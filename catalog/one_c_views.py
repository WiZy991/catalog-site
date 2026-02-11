"""
Views для интеграции с 1С - загрузка файлов и API синхронизация.
"""
import json
import csv
import time
import logging
import xml.etree.ElementTree as ET
from io import StringIO, BytesIO
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.mail import send_mail

from .models import Product, ProductCharacteristic, Category, SyncLog
from .serializers import validate_sync_request, validate_product

logger = logging.getLogger(__name__)

# API ключ для доступа
ONE_C_API_KEY = getattr(settings, 'ONE_C_API_KEY', 'change-this-secret-key-in-production')


def get_client_ip(request):
    """Получить IP адрес клиента."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_token_auth(request):
    """Проверка токена авторизации."""
    # Проверяем токен в заголовке или в теле запроса (для JSON)
    token = None
    
    # Из заголовка
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.replace('Bearer ', '')
    elif 'X-API-Key' in request.headers:
        token = request.headers.get('X-API-Key')
    
    # Из тела запроса (для JSON)
    if not token and request.content_type == 'application/json':
        try:
            body = json.loads(request.body.decode('utf-8'))
            token = body.get('token')
        except:
            pass
    
    if not token or token != ONE_C_API_KEY:
        return False, 'Неверный токен авторизации'
    
    return True, None


def parse_csv_file(file):
    """Парсинг CSV файла."""
    try:
        # Пытаемся определить кодировку
        content = file.read()
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = content.decode('cp1251')
            except UnicodeDecodeError:
                text = content.decode('utf-8', errors='ignore')
        
        reader = csv.DictReader(StringIO(text))
        products = []
        for row in reader:
            # Нормализуем ключи (убираем пробелы, приводим к нижнему регистру)
            normalized_row = {}
            for key, value in row.items():
                normalized_key = key.strip().lower().replace(' ', '_')
                normalized_row[normalized_key] = value.strip() if value else ''
            
            # Преобразуем в формат для сериализатора
            product_data = {
                'sku': normalized_row.get('sku') or normalized_row.get('артикул') or normalized_row.get('article', ''),
                'name': normalized_row.get('name') or normalized_row.get('название') or normalized_row.get('наименование', ''),
                'description': normalized_row.get('description') or normalized_row.get('описание', ''),
                'price': normalized_row.get('price') or normalized_row.get('цена', '0'),
                'old_price': normalized_row.get('old_price') or normalized_row.get('старая_цена', ''),
                'stock': normalized_row.get('stock') or normalized_row.get('остаток') or normalized_row.get('количество', '0'),
                'category': normalized_row.get('category') or normalized_row.get('категория', ''),
                'is_active': normalized_row.get('is_active', 'true').lower() in ('true', '1', 'да', 'yes'),
            }
            
            # Характеристики из CSV (если есть колонки с характеристиками)
            characteristics = []
            for key, value in normalized_row.items():
                if key not in ['sku', 'name', 'description', 'price', 'old_price', 'stock', 'category', 'is_active']:
                    if value:
                        characteristics.append({'name': key.replace('_', ' ').title(), 'value': value})
            
            if characteristics:
                product_data['characteristics'] = characteristics
            
            if product_data['sku']:
                products.append(product_data)
        
        return products
    except Exception as e:
        raise ValueError(f'Ошибка парсинга CSV: {str(e)}')


def parse_xml_file(file):
    """Парсинг XML файла."""
    try:
        content = file.read()
        root = ET.fromstring(content)
        products = []
        
        # Ищем товары в XML
        for item in root.findall('.//product') or root.findall('.//item') or root.findall('.//товар'):
            product_data = {}
            
            # Базовые поля
            sku_elem = item.find('sku') or item.find('артикул') or item.find('article')
            name_elem = item.find('name') or item.find('название') or item.find('наименование')
            price_elem = item.find('price') or item.find('цена')
            
            if sku_elem is not None and sku_elem.text:
                product_data['sku'] = sku_elem.text.strip()
            else:
                continue  # Пропускаем товары без артикула
            
            if name_elem is not None:
                product_data['name'] = name_elem.text.strip() if name_elem.text else ''
            
            if price_elem is not None:
                product_data['price'] = price_elem.text.strip() if price_elem.text else '0'
            
            # Опциональные поля
            desc_elem = item.find('description') or item.find('описание')
            if desc_elem is not None:
                product_data['description'] = desc_elem.text.strip() if desc_elem.text else ''
            
            old_price_elem = item.find('old_price') or item.find('старая_цена')
            if old_price_elem is not None:
                product_data['old_price'] = old_price_elem.text.strip() if old_price_elem.text else ''
            
            stock_elem = item.find('stock') or item.find('остаток') or item.find('количество')
            if stock_elem is not None:
                product_data['stock'] = stock_elem.text.strip() if stock_elem.text else '0'
            
            category_elem = item.find('category') or item.find('категория')
            if category_elem is not None:
                product_data['category'] = category_elem.text.strip() if category_elem.text else ''
            
            is_active_elem = item.find('is_active') or item.find('активен')
            if is_active_elem is not None:
                product_data['is_active'] = is_active_elem.text.strip().lower() in ('true', '1', 'да', 'yes')
            else:
                product_data['is_active'] = True
            
            # Характеристики
            characteristics = []
            chars_elem = item.find('characteristics') or item.find('характеристики')
            if chars_elem is not None:
                for char_elem in chars_elem.findall('characteristic') or chars_elem.findall('характеристика'):
                    name_elem = char_elem.find('name') or char_elem.find('название')
                    value_elem = char_elem.find('value') or char_elem.find('значение')
                    if name_elem is not None and value_elem is not None:
                        characteristics.append({
                            'name': name_elem.text.strip() if name_elem.text else '',
                            'value': value_elem.text.strip() if value_elem.text else ''
                        })
            
            if characteristics:
                product_data['characteristics'] = characteristics
            
            products.append(product_data)
        
        return products
    except ET.ParseError as e:
        raise ValueError(f'Ошибка парсинга XML: {str(e)}')


def parse_json_file(file):
    """Парсинг JSON файла."""
    try:
        content = file.read()
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('utf-8', errors='ignore')
        
        data = json.loads(text)
        
        # Поддержка разных форматов JSON
        if isinstance(data, dict):
            if 'products' in data:
                products = data['products']
            elif 'token' in data and 'products' in data:
                products = data['products']
            else:
                products = [data]
        elif isinstance(data, list):
            products = data
        else:
            raise ValueError('Неверный формат JSON данных')
        
        return products
    except json.JSONDecodeError as e:
        raise ValueError(f'Ошибка парсинга JSON: {str(e)}')


def get_or_create_category(category_name):
    """Получить или создать категорию."""
    if not category_name:
        return None
    
    category, created = Category.objects.get_or_create(
        name=category_name.strip(),
        defaults={'is_active': True}
    )
    return category


def process_product(product_data, sync_log=None):
    """Обработка одного товара. Возвращает (product, error, was_created)."""
    try:
        # Валидация данных
        try:
            validated_data = validate_product(product_data)
        except Exception as e:
            error_msg = f"Ошибка валидации: {str(e)}"
            logger.warning(error_msg)
            if sync_log:
                sync_log.errors.append({
                    'sku': product_data.get('sku', 'unknown'),
                    'error': error_msg
                })
            return None, error_msg, False
        
        # Проверяем, существует ли товар с таким артикулом
        sku = validated_data['sku']
        existing_product = Product.objects.filter(article=sku).first()
        was_created = existing_product is None
        
        if was_created:
            # Создаем новый товар
            product = Product(
                article=sku,
                name=validated_data['name'],
                price=validated_data['price'],
                quantity=validated_data.get('stock', 0),
                is_active=validated_data.get('is_active', True),
            )
        else:
            # Обновляем существующий товар
            product = existing_product
        
        # Обновляем поля товара
        product.name = validated_data['name']
        product.price = validated_data['price']
        product.quantity = validated_data.get('stock', 0)
        product.is_active = validated_data.get('is_active', True)
        
        if validated_data.get('description'):
            product.description = validated_data['description']
        
        if validated_data.get('old_price'):
            product.old_price = validated_data['old_price']
        
        # Категория
        if validated_data.get('category'):
            category = get_or_create_category(validated_data['category'])
            if category:
                product.category = category
        
        # Обновляем наличие
        if product.quantity > 0:
            product.availability = 'in_stock'
        else:
            product.availability = 'out_of_stock'
        
        product.save()
        
        # Обработка характеристик
        if validated_data.get('characteristics'):
            # Удаляем старые характеристики
            ProductCharacteristic.objects.filter(product=product).delete()
            
            # Создаем новые
            for idx, char_data in enumerate(validated_data['characteristics']):
                ProductCharacteristic.objects.create(
                    product=product,
                    name=char_data['name'],
                    value=char_data['value'],
                    order=idx
                )
        
        return product, None, was_created
        
    except Exception as e:
        error_msg = f"Ошибка обработки товара {product_data.get('sku', 'unknown')}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if sync_log:
            sync_log.errors.append({
                'sku': product_data.get('sku', 'unknown'),
                'error': error_msg
            })
        return None, error_msg, False


@csrf_exempt
@require_http_methods(["POST"])
def file_upload_view(request):
    """View для загрузки файлов (CSV, XML, JSON)."""
    start_time = time.time()
    sync_log = None
    
    try:
        # Проверка авторизации
        has_access, error_message = check_token_auth(request)
        if not has_access:
            sync_log = SyncLog.objects.create(
                operation_type='file_upload',
                status='unauthorized',
                message=error_message,
                request_ip=get_client_ip(request),
                processing_time=time.time() - start_time,
            )
            return JsonResponse({'status': 'error', 'message': error_message}, status=401)
        
        # Проверка наличия файла
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'Файл не найден в запросе'
            }, status=400)
        
        uploaded_file = request.FILES['file']
        filename = uploaded_file.name
        file_ext = filename.split('.')[-1].lower()
        
        # Определение формата и парсинг
        try:
            if file_ext == 'csv':
                products_data = parse_csv_file(uploaded_file)
                file_format = 'CSV'
            elif file_ext == 'xml':
                products_data = parse_xml_file(uploaded_file)
                file_format = 'XML'
            elif file_ext == 'json':
                products_data = parse_json_file(uploaded_file)
                file_format = 'JSON'
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Неподдерживаемый формат файла: {file_ext}. Поддерживаются: CSV, XML, JSON'
                }, status=400)
        except ValueError as e:
            sync_log = SyncLog.objects.create(
                operation_type='file_upload',
                status='error',
                message=str(e),
                request_ip=get_client_ip(request),
                request_format=file_ext.upper(),
                filename=filename,
                processing_time=time.time() - start_time,
            )
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        
        if not products_data:
            return JsonResponse({
                'status': 'error',
                'message': 'Файл не содержит данных'
            }, status=400)
        
        # Обработка товаров в транзакции
        created_count = 0
        updated_count = 0
        errors = []
        
        # Создаем временный sync_log для передачи в process_product
        temp_sync_log = SyncLog(
            operation_type='file_upload',
            status='processing',
            errors=[],
        )
        
        with transaction.atomic():
            for product_data in products_data:
                product, error, was_created = process_product(product_data, sync_log=temp_sync_log)
                if product:
                    if was_created:
                        created_count += 1
                    else:
                        updated_count += 1
                elif error:
                    errors.append(error)
        
        # Создание лога
        processing_time = time.time() - start_time
        status = 'success' if not errors else ('partial' if created_count + updated_count > 0 else 'error')
        
        final_errors = (temp_sync_log.errors + errors)[:50]  # Ограничиваем количество ошибок
        
        sync_log = SyncLog.objects.create(
            operation_type='file_upload',
            status=status,
            message=f'Обработано {len(products_data)} товаров',
            processed_count=len(products_data),
            created_count=created_count,
            updated_count=updated_count,
            errors_count=len(final_errors),
            errors=final_errors,
            request_ip=get_client_ip(request),
            request_format=file_format,
            filename=filename,
            processing_time=processing_time,
        )
        
        # Отправка уведомления об ошибках (если есть)
        if errors and hasattr(settings, 'MANAGER_EMAIL'):
            try:
                send_mail(
                    subject=f'Ошибки синхронизации 1С - {filename}',
                    message=f'При синхронизации товаров из файла {filename} возникло {len(errors)} ошибок.\n\nПервые 10 ошибок:\n' + '\n'.join(errors[:10]),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.MANAGER_EMAIL],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f'Ошибка отправки email: {e}')
        
        # Ответ
        response_data = {
            'status': status,
            'processed': len(products_data),
            'created': created_count,
            'updated': updated_count,
            'errors': errors[:10] if errors else []
        }
        
        status_code = 200 if status == 'success' else (207 if status == 'partial' else 400)
        return JsonResponse(response_data, status=status_code)
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_message = str(e)
        logger.error(f'Ошибка загрузки файла: {error_message}', exc_info=True)
        
        if not sync_log:
            sync_log = SyncLog.objects.create(
                operation_type='file_upload',
                status='error',
                message=error_message,
                request_ip=get_client_ip(request),
                processing_time=processing_time,
            )
        
        return JsonResponse({
            'status': 'error',
            'message': 'Внутренняя ошибка сервера',
            'error': error_message
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def one_c_api_view(request):
    """API endpoint для синхронизации товаров от 1С (JSON)."""
    start_time = time.time()
    sync_log = None
    
    try:
        # Проверка авторизации
        has_access, error_message = check_token_auth(request)
        if not has_access:
            sync_log = SyncLog.objects.create(
                operation_type='api_sync',
                status='unauthorized',
                message=error_message,
                request_ip=get_client_ip(request),
                request_format='JSON',
                processing_time=time.time() - start_time,
            )
            return JsonResponse({'status': 'error', 'message': error_message}, status=401)
        
        # Парсинг JSON
        try:
            body = request.body.decode('utf-8')
            data = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            sync_log = SyncLog.objects.create(
                operation_type='api_sync',
                status='error',
                message=f'Ошибка парсинга JSON: {str(e)}',
                request_ip=get_client_ip(request),
                request_format='JSON',
                processing_time=time.time() - start_time,
            )
            return JsonResponse({
                'status': 'error',
                'message': f'Ошибка парсинга JSON: {str(e)}'
            }, status=400)
        
        # Валидация запроса
        try:
            validated_data = validate_sync_request(data)
        except Exception as e:
            error_msg = str(e)
            errors = getattr(e, 'errors', {})
            sync_log = SyncLog.objects.create(
                operation_type='api_sync',
                status='error',
                message=f'Ошибка валидации: {error_msg}',
                request_ip=get_client_ip(request),
                request_format='JSON',
                processing_time=time.time() - start_time,
            )
            return JsonResponse({
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': errors
            }, status=400)
        
        products_data = validated_data['products']
        
        if not products_data:
            return JsonResponse({
                'status': 'error',
                'message': 'Список товаров пуст'
            }, status=400)
        
        # Обработка товаров в транзакции
        created_count = 0
        updated_count = 0
        errors = []
        
        # Создаем временный sync_log для передачи в process_product
        temp_sync_log = SyncLog(
            operation_type='api_sync',
            status='processing',
            errors=[],
        )
        
        with transaction.atomic():
            for product_data in products_data:
                product, error, was_created = process_product(product_data, sync_log=temp_sync_log)
                if product:
                    if was_created:
                        created_count += 1
                    else:
                        updated_count += 1
                elif error:
                    errors.append(error)
        
        # Создание лога
        processing_time = time.time() - start_time
        status = 'success' if not errors else ('partial' if created_count + updated_count > 0 else 'error')
        
        final_errors = (temp_sync_log.errors + errors)[:50]  # Ограничиваем количество ошибок
        
        sync_log = SyncLog.objects.create(
            operation_type='api_sync',
            status=status,
            message=f'Обработано {len(products_data)} товаров',
            processed_count=len(products_data),
            created_count=created_count,
            updated_count=updated_count,
            errors_count=len(final_errors),
            errors=final_errors,
            request_ip=get_client_ip(request),
            request_format='JSON',
            processing_time=processing_time,
        )
        
        # Отправка уведомления об ошибках (если есть)
        if errors and hasattr(settings, 'MANAGER_EMAIL'):
            try:
                send_mail(
                    subject='Ошибки синхронизации 1С - API',
                    message=f'При синхронизации товаров через API возникло {len(errors)} ошибок.\n\nПервые 10 ошибок:\n' + '\n'.join(errors[:10]),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.MANAGER_EMAIL],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f'Ошибка отправки email: {e}')
        
        # Ответ
        response_data = {
            'status': status,
            'processed': len(products_data),
            'created': created_count,
            'updated': updated_count,
            'errors': errors[:10] if errors else []
        }
        
        status_code = 200 if status == 'success' else (207 if status == 'partial' else 400)
        return JsonResponse(response_data, status=status_code)
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_message = str(e)
        logger.error(f'Ошибка API синхронизации: {error_message}', exc_info=True)
        
        if not sync_log:
            sync_log = SyncLog.objects.create(
                operation_type='api_sync',
                status='error',
                message=error_message,
                request_ip=get_client_ip(request),
                request_format='JSON',
                processing_time=processing_time,
            )
        
        return JsonResponse({
            'status': 'error',
            'message': 'Внутренняя ошибка сервера',
            'error': error_message
        }, status=500)
