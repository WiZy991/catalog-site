"""
API views для интеграции с 1С.
"""
import json
import time
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError
import xml.etree.ElementTree as ET

from .models import Product, ProductImage, OneCExchangeLog

logger = logging.getLogger(__name__)

# API ключ для доступа (можно вынести в settings)
ONE_C_API_KEY = getattr(settings, 'ONE_C_API_KEY', 'change-this-secret-key-in-production')


def get_client_ip(request):
    """Получить IP адрес клиента."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_api_access(request):
    """Проверка доступа к API."""
    # Проверка API ключа из заголовка
    api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not api_key or api_key != ONE_C_API_KEY:
        return False, 'Неверный API ключ'
    
    return True, None


def parse_xml_data(xml_string):
    """Парсинг XML данных."""
    try:
        root = ET.fromstring(xml_string)
        products = []
        
        # Ищем товары в XML (адаптируйте под формат вашего XML)
        for item in root.findall('.//product') or root.findall('.//item') or root.findall('.//товар'):
            product_data = {}
            for child in item:
                tag = child.tag.lower()
                # Убираем namespace если есть
                if '}' in tag:
                    tag = tag.split('}')[1]
                product_data[tag] = child.text or ''
            products.append(product_data)
        
        return products
    except ET.ParseError as e:
        raise ValueError(f'Ошибка парсинга XML: {str(e)}')


def parse_json_data(json_string):
    """Парсинг JSON данных."""
    try:
        data = json.loads(json_string)
        
        # Поддержка разных форматов JSON
        if isinstance(data, dict):
            # Если это объект с ключом products или items
            products = data.get('products', data.get('items', data.get('товары', [])))
            if not isinstance(products, list):
                products = [data]
        elif isinstance(data, list):
            products = data
        else:
            raise ValueError('Неверный формат JSON данных')
        
        return products
    except json.JSONDecodeError as e:
        raise ValueError(f'Ошибка парсинга JSON: {str(e)}')


def normalize_product_data(product_data):
    """Нормализация данных товара из разных форматов (включая 1С)."""
    # Поддержка разных названий полей (русские/английские/1С)
    field_mapping = {
        'external_id': ['external_id', 'id', 'ид', 'id_1c', 'guid', 'uuid'],
        # Артикул1 - основной артикул бренда (CP01, FK16HR11)
        'article': ['article', 'артикул', 'артикул1', 'artikul', 'artikul1', 'part_number', 'номер'],
        # Артикул2 - OEM номер (11065-D9702, 90919-01243)
        'oem_number': ['oem_number', 'oem', 'артикул2', 'artikul2', 'oe_number', 'original_number'],
        # Марка - бренд
        'brand': ['brand', 'бренд', 'марка', 'производитель', 'manufacturer'],
        'name': ['name', 'название', 'title', 'наименование', 'наименование_для_печати', 'рабочее_наименование'],
        'category_name': ['category', 'категория', 'номенклатура', 'группа'],
        'price': ['price', 'цена', 'стоимость', 'розничная_цена'],
        'wholesale_price': ['wholesale_price', 'оптовая_цена', 'цена_опт', 'opt_price'],
        'quantity': ['quantity', 'количество', 'остаток', 'stock', 'qty'],
        # Двигатель - применимость по двигателям
        'engine': ['engine', 'двигатель', 'engines', 'мотор'],
        # Кузов - применимость по кузовам
        'body': ['body', 'кузов', 'body_type', 'кузова'],
        # Модель - применимость по моделям
        'model': ['model', 'модель', 'models', 'модели'],
        # Размер - может быть вольтаж (12V-11V), материал (IRIDIUM), размеры и т.д.
        'size': ['size', 'размер', 'dimensions', 'габариты'],
        # Другие поля характеристик
        'voltage': ['voltage', 'вольтаж', 'напряжение', 'v'],
        'year': ['year', 'год', 'годы', 'years'],
        'condition': ['condition', 'состояние', 'новый'],
        'color': ['color', 'цвет'],
        'side': ['side', 'l_r', 'лево_право', 'сторона'],
        'position': ['position', 'f_r', 'перед_зад', 'позиция'],
        'direction': ['direction', 'u_d', 'верх_низ', 'направление'],
        'note': ['note', 'примечание', 'comment', 'комментарий'],
        # Стандартные поля
        'properties': ['properties', 'свойства', 'характеристики', 'attributes'],
        'farpost_url': ['farpost_url', 'farpost', 'ссылка_фарпост', 'url'],
        'images': ['images', 'изображения', 'фото', 'photos', 'pictures'],
    }
    
    normalized = {}
    
    for target_field, source_fields in field_mapping.items():
        for source_field in source_fields:
            # Проверяем разные варианты написания (с подчеркиванием, без, с заглавными)
            for key in product_data.keys():
                key_normalized = key.lower().replace('_', '').replace('-', '').replace(' ', '')
                source_normalized = source_field.lower().replace('_', '').replace('-', '').replace(' ', '')
                if key_normalized == source_normalized:
                    value = product_data[key]
                    if value is not None and value != '':
                        normalized[target_field] = value
                        break
            if target_field in normalized:
                break
    
    return normalized


@csrf_exempt
@require_http_methods(["POST"])
def one_c_import(request):
    """
    API endpoint для импорта товаров из 1С.
    
    POST /api/1c/import
    
    Поддерживает форматы: JSON, XML
    
    Заголовки:
    - X-API-Key: API ключ для доступа
    
    Формат JSON:
    {
        "products": [
            {
                "external_id": "12345",
                "article": "ABC123",
                "brand": "BrandName",
                "name": "Product Name",
                "price": 1000.00,
                "quantity": 5,
                "properties": {"key": "value"},
                "farpost_url": "https://...",
                "images": ["url1", "url2"]
            }
        ]
    }
    """
    start_time = time.time()
    log_entry = None
    
    try:
        # Проверка доступа
        has_access, error_message = check_api_access(request)
        if not has_access:
            log_entry = OneCExchangeLog.objects.create(
                request_method=request.method,
                request_path=request.path,
                request_ip=get_client_ip(request),
                request_headers=dict(request.headers),
                request_body_size=len(request.body),
                status='unauthorized',
                status_code=401,
                error_message=error_message,
            )
            return JsonResponse({'error': error_message}, status=401)
        
        # Определение формата данных
        content_type = request.content_type or ''
        body = request.body.decode('utf-8')
        
        if 'xml' in content_type.lower() or body.strip().startswith('<'):
            # XML формат
            try:
                products_data = parse_xml_data(body)
                data_format = 'XML'
            except Exception as e:
                log_entry = OneCExchangeLog.objects.create(
                    request_method=request.method,
                    request_path=request.path,
                    request_ip=get_client_ip(request),
                    request_headers=dict(request.headers),
                    request_body_size=len(request.body),
                    request_format='XML',
                    status='error',
                    status_code=400,
                    error_message=str(e),
                )
                return JsonResponse({'error': f'Ошибка парсинга XML: {str(e)}'}, status=400)
        else:
            # JSON формат (по умолчанию)
            try:
                products_data = parse_json_data(body)
                data_format = 'JSON'
            except Exception as e:
                log_entry = OneCExchangeLog.objects.create(
                    request_method=request.method,
                    request_path=request.path,
                    request_ip=get_client_ip(request),
                    request_headers=dict(request.headers),
                    request_body_size=len(request.body),
                    request_format='JSON',
                    status='error',
                    status_code=400,
                    error_message=str(e),
                )
                return JsonResponse({'error': f'Ошибка парсинга JSON: {str(e)}'}, status=400)
        
        if not products_data:
            return JsonResponse({'error': 'Нет данных для импорта'}, status=400)
        
        # Статистика
        total_products = len(products_data)
        updated_count = 0
        created_count = 0
        hidden_count = 0
        errors = []
        
        # Получаем все external_id из запроса
        incoming_external_ids = set()
        for product_data in products_data:
            normalized = normalize_product_data(product_data)
            external_id = normalized.get('external_id')
            if external_id:
                incoming_external_ids.add(str(external_id))
        
        # Скрываем товары, которых нет в выгрузке (если они были импортированы из 1С)
        if incoming_external_ids:
            hidden_count = Product.objects.filter(
                external_id__isnull=False
            ).exclude(
                external_id__in=incoming_external_ids
            ).update(is_active=False)
        
        # Обработка товаров
        with transaction.atomic():
            for idx, product_data in enumerate(products_data):
                try:
                    normalized = normalize_product_data(product_data)
                    
                    # Обязательные поля
                    external_id = normalized.get('external_id')
                    if not external_id:
                        errors.append(f'Товар #{idx + 1}: отсутствует external_id')
                        continue
                    
                    external_id = str(external_id)
                    
                    # Проверка на дубликаты (если товар с таким external_id уже существует, но не этот)
                    existing_product = Product.objects.filter(external_id=external_id).first()
                    if existing_product:
                        # Обновляем существующий товар
                        product = existing_product
                        is_new = False
                    else:
                        # Создаем новый товар
                        product = Product()
                        product.external_id = external_id
                        is_new = True
                    
                    # Обновление полей
                    if 'article' in normalized:
                        product.article = str(normalized['article'])[:100]
                    if 'brand' in normalized:
                        product.brand = str(normalized['brand'])[:200]
                    if 'name' in normalized:
                        product.name = str(normalized['name'])[:500]
                    if 'price' in normalized:
                        try:
                            price = float(str(normalized['price']).replace(',', '.').replace(' ', ''))
                            product.price = max(0, price)
                        except (ValueError, TypeError):
                            pass
                    if 'wholesale_price' in normalized:
                        try:
                            wprice = float(str(normalized['wholesale_price']).replace(',', '.').replace(' ', ''))
                            product.wholesale_price = max(0, wprice)
                        except (ValueError, TypeError):
                            pass
                    if 'quantity' in normalized:
                        try:
                            quantity = int(float(str(normalized['quantity']).replace(',', '.').replace(' ', '')))
                            product.quantity = max(0, quantity)
                        except (ValueError, TypeError):
                            pass
                    
                    # OEM номер (Артикул2) → cross_numbers
                    if 'oem_number' in normalized:
                        oem = str(normalized['oem_number']).strip()
                        if oem:
                            # Добавляем к существующим кросс-номерам, если они есть
                            existing_cross = product.cross_numbers or ''
                            if oem not in existing_cross:
                                if existing_cross:
                                    product.cross_numbers = f"{existing_cross}, {oem}"
                                else:
                                    product.cross_numbers = oem
                    
                    # Формируем применимость из полей: двигатель, кузов, модель
                    applicability_parts = []
                    if 'engine' in normalized and normalized['engine']:
                        applicability_parts.append(str(normalized['engine']).strip())
                    if 'body' in normalized and normalized['body']:
                        applicability_parts.append(str(normalized['body']).strip())
                    if 'model' in normalized and normalized['model']:
                        applicability_parts.append(str(normalized['model']).strip())
                    if applicability_parts:
                        product.applicability = ', '.join(applicability_parts)
                    
                    # Размер → характеристики (может быть вольтаж, материал, габариты)
                    characteristics_parts = []
                    if 'size' in normalized and normalized['size']:
                        size_val = str(normalized['size']).strip()
                        # Определяем тип значения
                        if 'V' in size_val.upper() and any(c.isdigit() for c in size_val):
                            # Это вольтаж (12V, 12V-11V, 24V)
                            characteristics_parts.append(f"Напряжение: {size_val}")
                        elif size_val.upper() in ['IRIDIUM', 'PLATINUM', 'COPPER', 'ИРИДИЙ', 'ПЛАТИНА']:
                            # Это материал
                            characteristics_parts.append(f"Материал: {size_val}")
                        else:
                            # Прочий размер
                            characteristics_parts.append(f"Размер: {size_val}")
                    
                    if 'voltage' in normalized and normalized['voltage']:
                        characteristics_parts.append(f"Напряжение: {normalized['voltage']}")
                    if 'year' in normalized and normalized['year']:
                        characteristics_parts.append(f"Год: {normalized['year']}")
                    if 'color' in normalized and normalized['color']:
                        characteristics_parts.append(f"Цвет: {normalized['color']}")
                    if 'side' in normalized and normalized['side']:
                        characteristics_parts.append(f"Сторона: {normalized['side']}")
                    if 'position' in normalized and normalized['position']:
                        characteristics_parts.append(f"Позиция: {normalized['position']}")
                    if 'direction' in normalized and normalized['direction']:
                        characteristics_parts.append(f"Направление: {normalized['direction']}")
                    if 'note' in normalized and normalized['note']:
                        characteristics_parts.append(f"Примечание: {normalized['note']}")
                    
                    if characteristics_parts:
                        # Объединяем с существующими характеристиками
                        existing_chars = product.characteristics or ''
                        new_chars = '\n'.join(characteristics_parts)
                        if existing_chars:
                            product.characteristics = f"{existing_chars}\n{new_chars}"
                        else:
                            product.characteristics = new_chars
                    
                    # Состояние товара
                    if 'condition' in normalized:
                        cond_val = str(normalized['condition']).strip().lower()
                        if cond_val in ['да', 'новый', 'new', 'yes', '1', 'true']:
                            product.condition = 'new'
                        elif cond_val in ['нет', 'б/у', 'used', 'no', '0', 'false', 'бу']:
                            product.condition = 'used'
                    
                    if 'properties' in normalized:
                        if isinstance(normalized['properties'], dict):
                            product.properties = normalized['properties']
                        elif isinstance(normalized['properties'], str):
                            try:
                                product.properties = json.loads(normalized['properties'])
                            except:
                                product.properties = {}
                    if 'farpost_url' in normalized:
                        product.farpost_url = str(normalized['farpost_url'])[:200]
                    
                    # Устанавливаем активность
                    product.is_active = True
                    
                    # Сохранение товара
                    product.save()
                    
                    # Обработка изображений
                    if 'images' in normalized:
                        images = normalized['images']
                        if isinstance(images, str):
                            # Если это строка, пытаемся распарсить как JSON
                            try:
                                images = json.loads(images)
                            except:
                                images = [images] if images else []
                        elif not isinstance(images, list):
                            images = []
                        
                        # Удаляем старые изображения (опционально, можно оставить)
                        # ProductImage.objects.filter(product=product).delete()
                        
                        # Добавляем новые изображения (только URL, загрузка файлов не реализована)
                        # В реальном проекте можно добавить загрузку изображений по URL
                        for img_url in images[:10]:  # Максимум 10 изображений
                            if img_url and isinstance(img_url, str):
                                # Здесь можно добавить логику загрузки изображений по URL
                                # Пока просто пропускаем
                                pass
                    
                    if is_new:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                except Exception as e:
                    error_msg = f'Товар #{idx + 1}: {str(e)}'
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
        
        # Время обработки
        processing_time = time.time() - start_time
        
        # Создание лога
        log_entry = OneCExchangeLog.objects.create(
            request_method=request.method,
            request_path=request.path,
            request_ip=get_client_ip(request),
            request_headers=dict(request.headers),
            request_body_size=len(request.body),
            request_format=data_format,
            status='success' if not errors else 'error',
            status_code=200 if not errors else 207,  # 207 Multi-Status если есть ошибки
            total_products=total_products,
            updated_products=updated_count,
            created_products=created_count,
            hidden_products=hidden_count,
            errors_count=len(errors),
            error_message='\n'.join(errors) if errors else '',
            response_data={
                'total': total_products,
                'updated': updated_count,
                'created': created_count,
                'hidden': hidden_count,
                'errors': len(errors),
            },
            processing_time=processing_time,
        )
        
        # Ответ
        response_data = {
            'success': True,
            'total': total_products,
            'updated': updated_count,
            'created': created_count,
            'hidden': hidden_count,
            'errors_count': len(errors),
        }
        
        if errors:
            response_data['errors'] = errors[:10]  # Первые 10 ошибок
        
        status_code = 200 if not errors else 207
        return JsonResponse(response_data, status=status_code)
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_message = str(e)
        logger.error(f'Ошибка импорта из 1С: {error_message}', exc_info=True)
        
        if not log_entry:
            log_entry = OneCExchangeLog.objects.create(
                request_method=request.method,
                request_path=request.path,
                request_ip=get_client_ip(request),
                request_headers=dict(request.headers) if hasattr(request, 'headers') else {},
                request_body_size=len(request.body) if hasattr(request, 'body') else 0,
                status='error',
                status_code=500,
                error_message=error_message,
                processing_time=processing_time,
            )
        
        return JsonResponse({'error': 'Внутренняя ошибка сервера', 'message': error_message}, status=500)

