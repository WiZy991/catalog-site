"""
Views для обработки стандартного протокола CommerceML 2 обмена с 1С.
Протокол разработан компаниями «1С» и «1С-Битрикс».
"""
import os
import json
import logging
import xml.etree.ElementTree as ET
from io import BytesIO
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from .models import Product, ProductCharacteristic, Category, SyncLog
from .serializers import validate_product, SerializerValidationError

logger = logging.getLogger(__name__)

# Настройки
EXCHANGE_DIR = getattr(settings, 'ONE_C_EXCHANGE_DIR', os.path.join(settings.MEDIA_ROOT, '1c_exchange'))
FILE_LIMIT = getattr(settings, 'ONE_C_FILE_LIMIT', 104857600)  # 100 MB по умолчанию
SUPPORT_ZIP = getattr(settings, 'ONE_C_SUPPORT_ZIP', True)

# Создаем директорию для обмена, если её нет
os.makedirs(EXCHANGE_DIR, exist_ok=True)


def get_client_ip(request):
    """Получить IP адрес клиента."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_basic_auth(request):
    """Проверка базовой HTTP авторизации (логин/пароль из админки Django)."""
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        if len(auth) == 2 and auth[0].lower() == 'basic':
            import base64
            try:
                username, password = base64.b64decode(auth[1]).decode('utf-8').split(':', 1)
                from django.contrib.auth import authenticate
                user = authenticate(request, username=username, password=password)
                if user and user.is_active and user.is_staff:
                    return True
            except Exception as e:
                logger.error(f"Ошибка проверки авторизации: {e}")
    return False


@csrf_exempt
@require_http_methods(["GET", "POST"])
def commerceml_exchange(request):
    """
    Обработчик стандартного протокола CommerceML 2 обмена с 1С.
    
    Параметры запроса:
    - type: catalog (тип обмена)
    - mode: checkauth, init, file, import (режим обмена)
    - filename: имя файла (для режимов file и import)
    """
    # Явное логирование ВСЕХ запросов
    exchange_type = request.GET.get('type', '')
    mode = request.GET.get('mode', '')
    filename = request.GET.get('filename', '')
    client_ip = get_client_ip(request)
    
    # Логируем ВСЕ запросы, даже если они не к CommerceML
    logger.info("=" * 80)
    logger.info(f"CommerceML запрос получен!")
    logger.info(f"  URL: {request.path}")
    logger.info(f"  Method: {request.method}")
    logger.info(f"  GET params: {dict(request.GET)}")
    logger.info(f"  Type: {exchange_type}")
    logger.info(f"  Mode: {mode}")
    logger.info(f"  Filename: {filename}")
    logger.info(f"  IP: {client_ip}")
    logger.info(f"  Headers: Authorization={bool(request.META.get('HTTP_AUTHORIZATION'))}")
    logger.info("=" * 80)
    
    # Проверяем тип обмена
    if exchange_type != 'catalog':
        logger.warning(f"Неподдерживаемый тип обмена: {exchange_type}")
        return HttpResponse('failure\nНеподдерживаемый тип обмена', status=400)
    
    # Обрабатываем режимы
    if mode == 'checkauth':
        logger.info("Обработка режима: checkauth")
        return handle_checkauth(request)
    elif mode == 'init':
        logger.info("Обработка режима: init")
        return handle_init(request)
    elif mode == 'file':
        logger.info(f"Обработка режима: file, filename={filename}")
        return handle_file(request, filename)
    elif mode == 'import':
        logger.info(f"Обработка режима: import, filename={filename}")
        return handle_import(request, filename)
    else:
        logger.warning(f"Неизвестный режим обмена: {mode}")
        return HttpResponse('failure\nНеизвестный режим обмена', status=400)


def handle_checkauth(request):
    """
    Режим A: Начало сеанса
    Проверка авторизации и установка Cookie.
    
    Возвращает три строки:
    - success
    - имя Cookie
    - значение Cookie
    """
    logger.info("handle_checkauth вызван")
    
    # Проверяем базовую HTTP авторизацию
    if not check_basic_auth(request):
        logger.warning("Ошибка авторизации в checkauth")
        return HttpResponse('failure\nОшибка авторизации', status=401)
    
    logger.info("Авторизация успешна, создаем сессию")
    
    # Генерируем Cookie для сессии
    import secrets
    cookie_name = '1c_exchange_session'
    cookie_value = secrets.token_urlsafe(32)
    
    logger.info(f"Создана сессия: {cookie_value[:20]}...")
    
    # Сохраняем сессию (можно использовать кеш или БД)
    from django.core.cache import cache
    cache.set(f'1c_session_{cookie_value}', True, timeout=3600)  # 1 час
    
    logger.info("Сессия сохранена в кеш, отправляем ответ")
    
    response = HttpResponse('success\n{}\n{}'.format(cookie_name, cookie_value))
    response.set_cookie(cookie_name, cookie_value, max_age=3600)
    return response


def check_session_cookie(request):
    """Проверка Cookie сессии."""
    cookie_name = '1c_exchange_session'
    cookie_value = request.COOKIES.get(cookie_name)
    
    logger.info(f"Проверка cookie: есть={bool(cookie_value)}, значение={cookie_value[:20] if cookie_value else 'None'}...")
    
    if not cookie_value:
        logger.warning("Cookie не передана в запросе")
        return False
    
    from django.core.cache import cache
    session_exists = cache.get(f'1c_session_{cookie_value}') is not None
    logger.info(f"Сессия в кеше: {session_exists}")
    
    # ВРЕМЕННО ДЛЯ ОТЛАДКИ: разрешаем доступ даже если сессия не найдена
    # Это поможет понять, доходят ли запросы до Django
    if not session_exists:
        logger.warning("⚠️ ВРЕМЕННО: Сессия не найдена в кеше, но разрешаем доступ для отладки")
        logger.warning("⚠️ Это временное решение для диагностики проблемы!")
        return True  # ВРЕМЕННО разрешаем доступ
    
    return session_exists


def handle_init(request):
    """
    Режим B: Запрос параметров от сайта
    
    Возвращает две строки:
    - zip=yes или zip=no
    - file_limit=<число>
    """
    logger.info("handle_init вызван")
    
    if not check_session_cookie(request):
        logger.warning("Сессия недействительна в init")
        return HttpResponse('failure\nСессия недействительна', status=401)
    
    logger.info("Сессия валидна, отправляем параметры")
    zip_support = 'yes' if SUPPORT_ZIP else 'no'
    response_text = f'zip={zip_support}\nfile_limit={FILE_LIMIT}'
    logger.info(f"Отправляем параметры: {response_text}")
    return HttpResponse(response_text)


def handle_file(request, filename):
    """
    Режим C: Выгрузка на сайт файлов обмена
    
    Принимает файл через POST и сохраняет его.
    Возвращает 'success' при успешной записи.
    """
    logger.info("=" * 80)
    logger.info(f"handle_file вызван: filename={filename}, method={request.method}")
    logger.info(f"  Cookies: {dict(request.COOKIES)}")
    logger.info(f"  Content-Length: {request.META.get('CONTENT_LENGTH', 'unknown')}")
    
    # ВРЕМЕННО: пропускаем проверку cookie для отладки
    logger.warning("⚠️ ВРЕМЕННО: пропускаем проверку cookie в handle_file")
    # if not check_session_cookie(request):
    #     logger.warning("Сессия недействительна в handle_file")
    #     return HttpResponse('failure\nСессия недействительна', status=401)
    
    if request.method != 'POST':
        logger.warning(f"Неправильный метод в handle_file: {request.method}")
        return HttpResponse('failure\nТребуется POST запрос', status=405)
    
    if not filename:
        logger.warning("Не указано имя файла в handle_file")
        return HttpResponse('failure\nНе указано имя файла', status=400)
    
    try:
        # Получаем содержимое файла
        file_content = request.body
        logger.info(f"Получен файл {filename}, размер: {len(file_content)} байт")
        
        if len(file_content) > FILE_LIMIT:
            logger.error(f"Файл {filename} превышает лимит: {len(file_content)} > {FILE_LIMIT}")
            return HttpResponse('failure\nФайл превышает лимит размера', status=413)
        
        # Проверяем, что директория существует
        os.makedirs(EXCHANGE_DIR, exist_ok=True)
        logger.info(f"Директория обмена: {EXCHANGE_DIR}")
        
        # Сохраняем файл
        file_path = os.path.join(EXCHANGE_DIR, filename)
        logger.info(f"Сохраняем файл в: {file_path}")
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Проверяем, что файл действительно сохранен
        if os.path.exists(file_path):
            actual_size = os.path.getsize(file_path)
            logger.info(f"Файл успешно сохранен: {filename}, размер: {actual_size} байт")
        else:
            logger.error(f"Файл не найден после сохранения: {file_path}")
            return HttpResponse('failure\nОшибка сохранения файла', status=500)
        
        return HttpResponse('success')
        
    except Exception as e:
        logger.error(f"Ошибка сохранения файла {filename}: {e}", exc_info=True)
        return HttpResponse(f'failure\nОшибка сохранения файла: {str(e)}', status=500)


def handle_import(request, filename):
    """
    Режим D: Пошаговая загрузка данных
    
    Обрабатывает файл CommerceML 2 и импортирует товары.
    
    Возвращает:
    - progress - если обработка еще не завершена
    - success - при успешном завершении
    - failure - при ошибке
    """
    logger.info("=" * 80)
    logger.info(f"handle_import вызван: filename={filename}")
    logger.info(f"  Cookies: {dict(request.COOKIES)}")
    
    # ВРЕМЕННО: пропускаем проверку cookie для отладки
    logger.warning("⚠️ ВРЕМЕННО: пропускаем проверку cookie в handle_import")
    # if not check_session_cookie(request):
    #     logger.warning("Сессия недействительна в handle_import")
    #     return HttpResponse('failure\nСессия недействительна', status=401)
    
    if not filename:
        logger.warning("Не указано имя файла в handle_import")
        return HttpResponse('failure\nНе указано имя файла', status=400)
    
    file_path = os.path.join(EXCHANGE_DIR, filename)
    logger.info(f"Ищем файл: {file_path}")
    logger.info(f"Директория существует: {os.path.exists(EXCHANGE_DIR)}")
    logger.info(f"Файл существует: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        # Проверим, какие файлы есть в директории
        if os.path.exists(EXCHANGE_DIR):
            existing_files = os.listdir(EXCHANGE_DIR)
            logger.error(f"Файл не найден: {file_path}")
            logger.error(f"Существующие файлы в директории: {existing_files}")
        else:
            logger.error(f"Директория обмена не существует: {EXCHANGE_DIR}")
        return HttpResponse('failure\nФайл не найден', status=404)
    
    logger.info(f"Начало обработки файла: {filename}, размер: {os.path.getsize(file_path)} байт")
    
    try:
        # Парсим и обрабатываем файл CommerceML 2
        result = process_commerceml_file(file_path, filename, request)
        
        logger.info(f"Результат обработки файла {filename}: статус={result.get('status')}, обработано={result.get('processed', 0)}")
        
        if result['status'] == 'success':
            return HttpResponse('success')
        elif result['status'] == 'progress':
            progress_info = result.get('progress', '')
            return HttpResponse(f'progress\n{progress_info}')
        else:
            error_msg = result.get('error', 'Неизвестная ошибка')
            logger.error(f"Ошибка обработки файла {filename}: {error_msg}")
            return HttpResponse(f'failure\n{error_msg}', status=500)
            
    except Exception as e:
        logger.error(f"Исключение при обработке файла {filename}: {e}", exc_info=True)
        return HttpResponse(f'failure\nОшибка обработки: {str(e)}', status=500)


def process_commerceml_file(file_path, filename, request=None):
    """
    Обработка файла CommerceML 2.
    
    Парсит XML в формате CommerceML 2 и импортирует товары в базу данных.
    """
    start_time = timezone.now()
    
    logger.info(f"Начало обработки файла CommerceML: {filename}")
    
    try:
        # Проверяем размер файла
        file_size = os.path.getsize(file_path)
        logger.info(f"Размер файла: {file_size} байт")
        
        # Парсим XML
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        logger.info(f"Корневой элемент XML: {root.tag}")
        
        # Определяем namespace CommerceML
        namespaces = {
            'cml': 'http://v8.1c.ru/8.3/commerceml',
            '': 'http://v8.1c.ru/8.3/commerceml'
        }
        
        # Ищем каталог товаров
        catalog = root.find('.//catalog', namespaces) or root.find('.//Каталог', namespaces)
        
        if catalog is None:
            # Попробуем найти без namespace
            catalog = root.find('.//catalog') or root.find('.//Каталог')
            if catalog is None:
                logger.error(f"Каталог не найден в файле. Корневой элемент: {root.tag}")
                # Выведем все дочерние элементы для отладки
                logger.error(f"Дочерние элементы корня: {[child.tag for child in root]}")
                return {'status': 'failure', 'error': 'Каталог не найден в файле'}
        
        logger.info(f"Каталог найден: {catalog.tag}")
        
        # Извлекаем товары
        products_data = []
        
        # Ищем товары в разных возможных местах
        products_elements = (
            catalog.findall('.//catalog:Товары/catalog:Товар', namespaces) or
            catalog.findall('.//Товары/Товар') or
            catalog.findall('.//catalog:Товар', namespaces) or
            catalog.findall('.//Товар')
        )
        
        logger.info(f"Найдено элементов товаров: {len(products_elements)}")
        
        for idx, product_elem in enumerate(products_elements):
            product_data = parse_commerceml_product(product_elem, namespaces)
            if product_data:
                products_data.append(product_data)
                if idx < 3:  # Логируем первые 3 товара для отладки
                    logger.info(f"Товар #{idx+1}: sku={product_data.get('sku')}, name={product_data.get('name')[:50] if product_data.get('name') else 'N/A'}")
            else:
                logger.warning(f"Товар #{idx+1}: не удалось распарсить (нет обязательных полей)")
        
        logger.info(f"Всего распарсено товаров: {len(products_data)}")
        
        if not products_data:
            logger.warning("Товары не найдены в файле после парсинга")
            return {'status': 'success', 'message': 'Товары не найдены в файле'}
        
        # Обрабатываем товары в транзакции
        processed_count = 0
        created_count = 0
        updated_count = 0
        errors = []
        
        logger.info(f"Начало обработки {len(products_data)} товаров в транзакции")
        
        with transaction.atomic():
            for idx, product_data in enumerate(products_data):
                try:
                    product, error, was_created = process_product_from_commerceml(product_data)
                    if product:
                        processed_count += 1
                        if was_created:
                            created_count += 1
                            logger.info(f"Создан товар: {product.article} - {product.name}")
                        else:
                            updated_count += 1
                            logger.debug(f"Обновлен товар: {product.article} - {product.name}")
                    elif error:
                        error_info = {
                            'sku': product_data.get('sku', 'unknown'),
                            'error': error
                        }
                        errors.append(error_info)
                        logger.warning(f"Ошибка обработки товара {product_data.get('sku', 'unknown')}: {error}")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Исключение при обработке товара {product_data.get('sku', 'unknown')}: {error_msg}", exc_info=True)
                    errors.append({
                        'sku': product_data.get('sku', 'unknown'),
                        'error': error_msg
                    })
        
        logger.info(f"Обработка завершена: обработано={processed_count}, создано={created_count}, обновлено={updated_count}, ошибок={len(errors)}")
        
        # Создаем лог синхронизации
        processing_time = (timezone.now() - start_time).total_seconds()
        
        request_ip = get_client_ip(request) if request else None
        
        sync_log = SyncLog.objects.create(
            operation_type='file_upload',
            status='success' if not errors else 'partial',
            message=f'Обработано товаров из файла {filename}',
            processed_count=processed_count,
            created_count=created_count,
            updated_count=updated_count,
            errors_count=len(errors),
            errors=errors,
            request_ip=request_ip,
            request_format='CommerceML 2',
            filename=filename,
            processing_time=processing_time
        )
        
        logger.info(f"Импорт завершен: обработано {processed_count}, создано {created_count}, обновлено {updated_count}, ошибок {len(errors)}")
        
        return {
            'status': 'success',
            'processed': processed_count,
            'created': created_count,
            'updated': updated_count,
            'errors': len(errors)
        }
        
    except ET.ParseError as e:
        return {'status': 'failure', 'error': f'Ошибка парсинга XML: {str(e)}'}
    except Exception as e:
        logger.error(f"Ошибка обработки файла CommerceML: {e}", exc_info=True)
        return {'status': 'failure', 'error': str(e)}


def parse_commerceml_product(product_elem, namespaces):
    """
    Парсит элемент товара из CommerceML 2 XML.
    
    Возвращает словарь с данными товара в формате, совместимом с validate_product.
    """
    product_data = {}
    
    # Идентификатор товара (Ид)
    id_elem = product_elem.find('catalog:Ид', namespaces) or product_elem.find('Ид')
    if id_elem is not None and id_elem.text:
        product_data['sku'] = id_elem.text.strip()
        product_data['external_id'] = id_elem.text.strip()
    
    # Артикул
    article_elem = product_elem.find('catalog:Артикул', namespaces) or product_elem.find('Артикул')
    if article_elem is not None and article_elem.text:
        product_data['article'] = article_elem.text.strip()
        if 'sku' not in product_data:
            product_data['sku'] = article_elem.text.strip()
    
    # Наименование
    name_elem = product_elem.find('catalog:Наименование', namespaces) or product_elem.find('Наименование')
    if name_elem is not None and name_elem.text:
        product_data['name'] = name_elem.text.strip()
    
    # Описание
    description_elem = product_elem.find('catalog:Описание', namespaces) or product_elem.find('Описание')
    if description_elem is not None and description_elem.text:
        product_data['description'] = description_elem.text.strip()
    
    # Цены (ищем в предложениях)
    # В CommerceML цены обычно в отдельном файле предложений, но могут быть и здесь
    price_elem = product_elem.find('.//catalog:ЦенаЗаЕдиницу', namespaces) or product_elem.find('.//ЦенаЗаЕдиницу')
    if price_elem is not None and price_elem.text:
        try:
            product_data['price'] = float(price_elem.text.strip().replace(',', '.'))
        except (ValueError, AttributeError):
            pass
    
    # Остатки (ищем в предложениях)
    quantity_elem = product_elem.find('.//catalog:Количество', namespaces) or product_elem.find('.//Количество')
    if quantity_elem is not None and quantity_elem.text:
        try:
            product_data['stock'] = int(float(quantity_elem.text.strip().replace(',', '.')))
        except (ValueError, AttributeError):
            pass
    
    # Категория (группа)
    group_elem = product_elem.find('catalog:Группы/catalog:Ид', namespaces) or product_elem.find('Группы/Ид')
    if group_elem is not None and group_elem.text:
        # Нужно найти название группы по Ид
        # Пока просто сохраняем Ид, название найдем позже
        product_data['category_id'] = group_elem.text.strip()
    
    # Характеристики
    characteristics = []
    props_elem = product_elem.find('catalog:ЗначенияСвойств', namespaces) or product_elem.find('ЗначенияСвойств')
    if props_elem is not None:
        for prop_elem in props_elem.findall('catalog:ЗначенияСвойства', namespaces) or props_elem.findall('ЗначенияСвойства'):
            prop_id = prop_elem.find('catalog:Ид', namespaces) or prop_elem.find('Ид')
            prop_value = prop_elem.find('catalog:Значение', namespaces) or prop_elem.find('Значение')
            
            if prop_id is not None and prop_value is not None:
                # Нужно найти название свойства по Ид
                # Пока используем Ид как название
                prop_name = prop_id.text.strip() if prop_id.text else 'Свойство'
                prop_val = prop_value.text.strip() if prop_value.text else ''
                
                if prop_name and prop_val:
                    characteristics.append({
                        'name': prop_name,
                        'value': prop_val
                    })
    
    if characteristics:
        product_data['characteristics'] = characteristics
    
    # Активность
    product_data['is_active'] = True
    
    return product_data if product_data.get('sku') and product_data.get('name') else None


def process_offers_file(root, namespaces, filename, request=None):
    """
    Обрабатывает файл предложений (offers.xml) - обновляет цены и остатки.
    """
    logger.info("Обработка файла предложений (offers.xml)")
    
    start_time = timezone.now()
    processed_count = 0
    updated_count = 0
    errors = []
    
    # Ищем предложения
    offers = (
        root.findall('.//Предложение', namespaces) or
        root.findall('.//catalog:Предложение', namespaces) or
        root.findall('.//Предложение')
    )
    
    logger.info(f"Найдено предложений: {len(offers)}")
    
    if not offers:
        return {'status': 'success', 'message': 'Предложения не найдены в файле'}
    
    with transaction.atomic():
        for offer_elem in offers:
            try:
                # Ищем Ид товара
                product_id_elem = offer_elem.find('.//Ид', namespaces) or offer_elem.find('.//Ид')
                if product_id_elem is None or not product_id_elem.text:
                    continue
                
                product_id = product_id_elem.text.strip()
                
                # Ищем товар по external_id
                product = Product.objects.filter(external_id=product_id).first()
                if not product:
                    # Пробуем по артикулу
                    product = Product.objects.filter(article=product_id).first()
                
                if not product:
                    logger.warning(f"Товар с Ид {product_id} не найден в базе")
                    continue
                
                # Обновляем цену
                price_elem = offer_elem.find('.//ЦенаЗаЕдиницу', namespaces) or offer_elem.find('.//ЦенаЗаЕдиницу')
                if price_elem is not None and price_elem.text:
                    try:
                        price = float(price_elem.text.strip().replace(',', '.'))
                        product.price = price
                    except (ValueError, AttributeError):
                        pass
                
                # Обновляем остаток
                quantity_elem = offer_elem.find('.//Количество', namespaces) or offer_elem.find('.//Количество')
                if quantity_elem is not None and quantity_elem.text:
                    try:
                        quantity = int(float(quantity_elem.text.strip().replace(',', '.')))
                        product.quantity = quantity
                        if quantity > 0:
                            product.availability = 'in_stock'
                        else:
                            product.availability = 'out_of_stock'
                    except (ValueError, AttributeError):
                        pass
                
                product.save()
                processed_count += 1
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Ошибка обработки предложения: {e}", exc_info=True)
                errors.append({
                    'offer_id': product_id if 'product_id' in locals() else 'unknown',
                    'error': str(e)
                })
    
    processing_time = (timezone.now() - start_time).total_seconds()
    request_ip = get_client_ip(request) if request else None
    
    sync_log = SyncLog.objects.create(
        operation_type='file_upload',
        status='success' if not errors else 'partial',
        message=f'Обработано предложений из файла {filename}',
        processed_count=processed_count,
        created_count=0,
        updated_count=updated_count,
        errors_count=len(errors),
        errors=errors,
        request_ip=request_ip,
        request_format='CommerceML 2 (offers)',
        filename=filename,
        processing_time=processing_time
    )
    
    logger.info(f"Обработка предложений завершена: обработано {processed_count}, обновлено {updated_count}, ошибок {len(errors)}")
    
    return {
        'status': 'success',
        'processed': processed_count,
        'created': 0,
        'updated': updated_count,
        'errors': len(errors)
    }


def process_product_from_commerceml(product_data):
    """
    Обрабатывает товар из CommerceML формата.
    Использует ту же логику, что и process_product из one_c_views.py.
    """
    from .one_c_views import process_product
    
    # Преобразуем данные в формат, ожидаемый process_product
    # process_product ожидает sku, name, price, stock, category, characteristics, is_active
    
    # Если есть external_id, используем его как sku
    if 'external_id' in product_data and product_data['external_id']:
        product_data['sku'] = product_data['external_id']
    elif 'article' in product_data and product_data['article']:
        if 'sku' not in product_data or not product_data['sku']:
            product_data['sku'] = product_data['article']
    
    # Убеждаемся, что есть sku
    if 'sku' not in product_data or not product_data['sku']:
        return None, "Отсутствует идентификатор товара (Ид или Артикул)", False
    
    # Обрабатываем категорию
    if 'category_id' in product_data:
        # Пока не обрабатываем категорию по Ид, можно добавить позже
        pass
    
    # Вызываем стандартную функцию обработки
    return process_product(product_data, sync_log=None)
