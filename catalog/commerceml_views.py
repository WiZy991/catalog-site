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
    
    # КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ - записываем в файл напрямую для гарантии
    import os
    from django.conf import settings
    
    # Определяем путь к файлу логов
    log_file_path = os.path.join(settings.BASE_DIR, 'logs', 'commerceml_requests.log')
    logs_dir = os.path.dirname(log_file_path)
    
    # Логируем информацию о путях в logger (это точно сработает)
    logger.info(f"CommerceML LOG: BASE_DIR={settings.BASE_DIR}")
    logger.info(f"CommerceML LOG: logs_dir={logs_dir}")
    logger.info(f"CommerceML LOG: log_file_path={log_file_path}")
    logger.info(f"CommerceML LOG: logs_dir exists={os.path.exists(logs_dir)}")
    logger.info(f"CommerceML LOG: logs_dir is writable={os.access(logs_dir, os.W_OK) if os.path.exists(logs_dir) else 'N/A'}")
    
    # Создаем директорию logs/ если её нет
    try:
        os.makedirs(logs_dir, exist_ok=True)
        logger.info(f"CommerceML LOG: Директория logs/ создана или уже существует")
    except Exception as e:
        error_msg = f"Ошибка создания директории logs/: {e}, BASE_DIR={settings.BASE_DIR}, logs_dir={logs_dir}"
        logger.error(error_msg)
        print(f"ERROR: {error_msg}")
    
    # Логируем в файл
    try:
        # Проверяем, можем ли мы записать в файл
        if os.path.exists(logs_dir):
            test_file = os.path.join(logs_dir, 'test_write.tmp')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.info(f"CommerceML LOG: Проверка записи в logs/ прошла успешно")
            except Exception as test_e:
                logger.error(f"CommerceML LOG: НЕ МОЖЕМ записать в logs/: {test_e}")
        
        # Пытаемся записать в файл логов
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"{timezone.now().strftime('%Y-%m-%d %H:%M:%S')} - CommerceML запрос получен!\n")
            f.write(f"  URL: {request.path}\n")
            f.write(f"  Full URL: {request.build_absolute_uri()}\n")
            f.write(f"  Method: {request.method}\n")
            f.write(f"  GET params: {dict(request.GET)}\n")
            f.write(f"  Type: {exchange_type}\n")
            f.write(f"  Mode: {mode}\n")
            f.write(f"  Filename: {filename}\n")
            f.write(f"  IP: {client_ip}\n")
            f.write(f"  User-Agent: {request.META.get('HTTP_USER_AGENT', 'None')}\n")
            f.write(f"  Authorization header: {bool(request.META.get('HTTP_AUTHORIZATION'))}\n")
            f.write(f"  Log file path: {log_file_path}\n")
            f.write(f"  BASE_DIR: {settings.BASE_DIR}\n")
            f.write(f"{'='*80}\n")
            f.flush()  # Принудительно записываем в файл
            os.fsync(f.fileno())  # Синхронизируем с диском
        logger.info(f"CommerceML LOG: Файл успешно записан: {log_file_path}")
        logger.info(f"CommerceML LOG: Файл существует: {os.path.exists(log_file_path)}")
        logger.info(f"CommerceML LOG: Размер файла: {os.path.getsize(log_file_path) if os.path.exists(log_file_path) else 'N/A'}")
    except Exception as e:
        # Логируем ошибку и в logger, и в print для гарантии
        error_msg = f"Ошибка записи в файл логов: {e}, путь: {log_file_path}, BASE_DIR: {settings.BASE_DIR}, logs_dir: {logs_dir}"
        logger.error(error_msg, exc_info=True)
        print(f"ERROR: {error_msg}")
    
    # Логируем ВСЕ запросы, даже если они не к CommerceML
    # Используем print для гарантированного вывода (временное решение)
    print("=" * 80)
    print(f"CommerceML запрос получен!")
    print(f"  URL: {request.path}")
    print(f"  Method: {request.method}")
    print(f"  GET params: {dict(request.GET)}")
    print(f"  Type: {exchange_type}")
    print(f"  Mode: {mode}")
    print(f"  Filename: {filename}")
    print(f"  IP: {client_ip}")
    print("=" * 80)
    
    # Также логируем через logger
    logger.info("=" * 80)
    logger.info(f"CommerceML запрос получен!")
    logger.info(f"  URL: {request.path}")
    logger.info(f"  Method: {request.method}")
    logger.info(f"  GET params: {dict(request.GET)}")
    logger.info(f"  Type: {exchange_type}")
    logger.info(f"  Mode: {mode}")
    logger.info(f"  Filename: {filename}")
    logger.info(f"  IP: {client_ip}")
    
    # Логируем ВСЕ заголовки, связанные с авторизацией и cookie
    logger.info(f"  Headers:")
    logger.info(f"    Authorization: {request.META.get('HTTP_AUTHORIZATION', 'None')}")
    logger.info(f"    Cookie header: {request.META.get('HTTP_COOKIE', 'None')}")
    logger.info(f"    All cookies: {dict(request.COOKIES)}")
    
    # Проверяем все заголовки, которые могут содержать cookie
    cookie_headers = {k: v for k, v in request.META.items() if 'COOKIE' in k.upper() or 'SESSION' in k.upper()}
    if cookie_headers:
        logger.info(f"    Cookie-related headers: {cookie_headers}")
    
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
    
    # Формируем ответ согласно протоколу CommerceML 2
    # Должно быть три строки:
    # 1. success
    # 2. имя Cookie
    # 3. значение Cookie
    response_text = f'success\n{cookie_name}\n{cookie_value}'
    logger.info(f"Отправляем ответ checkauth: {response_text[:100]}...")
    
    response = HttpResponse(response_text, content_type='text/plain; charset=utf-8')
    response.set_cookie(cookie_name, cookie_value, max_age=3600, path='/')
    logger.info("Ответ checkauth отправлен")
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
    logger.info("=" * 80)
    logger.info("handle_init вызван")
    logger.info(f"  Cookies: {dict(request.COOKIES)}")
    logger.info(f"  HTTP_COOKIE: {request.META.get('HTTP_COOKIE', 'None')}")
    
    # ВРЕМЕННО: пропускаем проверку cookie для отладки
    logger.warning("⚠️ ВРЕМЕННО: пропускаем проверку cookie в init")
    # if not check_session_cookie(request):
    #     logger.warning("Сессия недействительна в init")
    #     return HttpResponse('failure\nСессия недействительна', status=401)
    
    logger.info("Отправляем параметры обмена")
    zip_support = 'yes' if SUPPORT_ZIP else 'no'
    response_text = f'zip={zip_support}\nfile_limit={FILE_LIMIT}'
    logger.info(f"Ответ init: {response_text}")
    logger.info("=" * 80)
    return HttpResponse(response_text, content_type='text/plain; charset=utf-8')


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
            
            # Если это ZIP, распаковываем сразу
            if filename.lower().endswith('.zip'):
                logger.info("Обнаружен ZIP архив, распаковываем...")
                import zipfile
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(EXCHANGE_DIR)
                        extracted_files = zip_ref.namelist()
                        logger.info(f"Распаковано файлов: {len(extracted_files)}")
                        for ext_file in extracted_files[:5]:  # Логируем первые 5
                            logger.info(f"  - {ext_file}")
                        
                        # Обрабатываем распакованные XML файлы автоматически
                        for ext_file in extracted_files:
                            if ext_file.lower().endswith('.xml'):
                                ext_file_path = os.path.join(EXCHANGE_DIR, ext_file)
                                if os.path.exists(ext_file_path):
                                    logger.info(f"Автоматическая обработка распакованного файла: {ext_file}")
                                    try:
                                        result = process_commerceml_file(ext_file_path, ext_file, request)
                                        logger.info(f"Результат обработки {ext_file}: {result.get('status')}")
                                    except Exception as e:
                                        logger.error(f"Ошибка автоматической обработки {ext_file}: {e}", exc_info=True)
                except zipfile.BadZipFile:
                    logger.warning("Файл не является ZIP архивом, оставляем как есть")
                except Exception as e:
                    logger.error(f"Ошибка распаковки ZIP: {e}", exc_info=True)
                    # Не возвращаем ошибку, файл сохранен, можно попробовать обработать
            
            # Если это XML файл, обрабатываем автоматически
            elif filename.lower().endswith('.xml'):
                logger.info(f"Обнаружен XML файл, запускаем автоматическую обработку...")
                try:
                    # Запускаем обработку в фоне (не блокируем ответ 1С)
                    import threading
                    def process_in_background():
                        try:
                            logger.info(f"Начало фоновой обработки файла: {filename}")
                            result = process_commerceml_file(file_path, filename, request)
                            logger.info(f"Завершена обработка файла {filename}: статус={result.get('status')}, обработано={result.get('processed', 0)}")
                        except Exception as e:
                            logger.error(f"Ошибка фоновой обработки файла {filename}: {e}", exc_info=True)
                    
                    # Запускаем в отдельном потоке
                    thread = threading.Thread(target=process_in_background, daemon=True)
                    thread.start()
                    logger.info("Фоновая обработка файла запущена")
                except Exception as e:
                    logger.error(f"Ошибка запуска фоновой обработки: {e}", exc_info=True)
                    # Не возвращаем ошибку, файл сохранен
        else:
            logger.error(f"Файл не найден после сохранения: {file_path}")
            return HttpResponse('failure\nОшибка сохранения файла', status=500, content_type='text/plain; charset=utf-8')
        
        logger.info("=" * 80)
        return HttpResponse('success', content_type='text/plain; charset=utf-8')
        
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
    Поддерживает ZIP архивы (распаковывает автоматически).
    """
    start_time = timezone.now()
    
    logger.info(f"Начало обработки файла CommerceML: {filename}")
    
    try:
        # Проверяем размер файла
        file_size = os.path.getsize(file_path)
        logger.info(f"Размер файла: {file_size} байт")
        
        # Проверяем, не ZIP ли это
        xml_file_path = file_path
        if filename.lower().endswith('.zip'):
            logger.info("Обнаружен ZIP архив, распаковываем...")
            import zipfile
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # Распаковываем в ту же директорию
                    zip_ref.extractall(EXCHANGE_DIR)
                    # Ищем XML файлы в архиве
                    xml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.xml')]
                    if xml_files:
                        xml_file_path = os.path.join(EXCHANGE_DIR, xml_files[0])
                        logger.info(f"Распакован XML файл: {xml_files[0]}")
                    else:
                        logger.error("В ZIP архиве не найдено XML файлов")
                        return {'status': 'failure', 'error': 'В ZIP архиве не найдено XML файлов'}
            except zipfile.BadZipFile:
                logger.warning("Файл не является ZIP архивом, обрабатываем как XML")
            except Exception as e:
                logger.error(f"Ошибка распаковки ZIP: {e}", exc_info=True)
                return {'status': 'failure', 'error': f'Ошибка распаковки ZIP: {str(e)}'}
        
        # Парсим XML
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        logger.info(f"Корневой элемент XML: {root.tag}")
        
        # Автоматически определяем namespace из корневого элемента
        root_tag = root.tag
        if root_tag.startswith('{'):
            # Извлекаем namespace из тега
            namespace = root_tag[1:root_tag.index('}')]
            root_tag_name = root_tag[root_tag.index('}')+1:]
        else:
            namespace = None
            root_tag_name = root_tag
        
        # Определяем namespace CommerceML (поддерживаем разные варианты)
        namespaces = {}
        if namespace:
            # Используем найденный namespace
            namespaces['cml'] = namespace
            namespaces[''] = namespace
        else:
            # Стандартные namespace CommerceML
            namespaces['cml'] = 'http://v8.1c.ru/8.3/commerceml'
            namespaces[''] = 'http://v8.1c.ru/8.3/commerceml'
        
        # Также добавляем альтернативный namespace (urn:1C.ru:commerceml_2)
        namespaces['cml2'] = 'urn:1C.ru:commerceml_2'
        
        logger.info(f"Определен namespace: {namespace or 'стандартный'}")
        
        # Ищем каталог товаров или предложения
        # В CommerceML может быть два типа файлов:
        # 1. import.xml - каталог товаров (названия, описания)
        # 2. offers.xml - предложения (цены, остатки)
        
        # Сначала проверяем, не файл ли это предложений
        package = None
        if namespace:
            package = root.find(f'.//{{{namespace}}}ПакетПредложений')
        if package is None:
            package = root.find('.//ПакетПредложений')
        if package is None and 'catalog' in namespaces:
            try:
                package = root.find('.//catalog:ПакетПредложений', namespaces)
            except (KeyError, ValueError):
                pass
        
        if package is not None:
            logger.info("Обнаружен файл предложений (offers.xml) - обрабатываем цены и остатки")
            return process_offers_file(root, namespaces, filename, request)
        
        # Ищем каталог товаров
        catalog = None
        if namespace:
            catalog = root.find(f'.//{{{namespace}}}Каталог') or root.find(f'.//{{{namespace}}}catalog')
        if catalog is None:
            catalog = (
                root.find('.//catalog', namespaces) or 
                root.find('.//Каталог', namespaces) or
                root.find('.//catalog') or 
                root.find('.//Каталог')
            )
        
        if catalog is None:
            logger.error(f"Каталог не найден в файле. Корневой элемент: {root.tag}, namespace: {namespace or 'нет'}")
            # Выведем все дочерние элементы для отладки
            logger.error(f"Дочерние элементы корня: {[child.tag for child in root[:5]]}")
            return {'status': 'failure', 'error': 'Каталог не найден в файле'}
        
        logger.info(f"Каталог найден: {catalog.tag}")
        
        # Извлекаем товары
        products_data = []
        
        # Ищем товары в разных возможных местах
        products_elements = []
        if namespace:
            products_elements = (
                catalog.findall(f'.//{{{namespace}}}Товары/{{{namespace}}}Товар') or
                catalog.findall(f'.//{{{namespace}}}Товар')
            )
        if not products_elements:
            products_elements = (
                catalog.findall('.//catalog:Товары/catalog:Товар', namespaces) or
                catalog.findall('.//Товары/Товар') or
                catalog.findall('.//catalog:Товар', namespaces) or
                catalog.findall('.//Товар')
            )
        
        logger.info(f"Найдено элементов товаров: {len(products_elements)}")
        
        # Если товары не найдены, выводим структуру XML для отладки
        if not products_elements:
            logger.error("Товары не найдены в XML! Выводим структуру для отладки:")
            logger.error(f"Корневой элемент: {root.tag}")
            logger.error(f"Атрибуты корня: {root.attrib}")
            for child in root:
                logger.error(f"  Дочерний элемент: {child.tag}, атрибуты: {child.attrib}")
                for grandchild in child:
                    logger.error(f"    Внук: {grandchild.tag}, атрибуты: {grandchild.attrib}")
        
        for idx, product_elem in enumerate(products_elements):
            product_data = parse_commerceml_product(product_elem, namespaces, root)
            if product_data:
                products_data.append(product_data)
                if idx < 3:  # Логируем первые 3 товара для отладки
                    logger.info(f"Товар #{idx+1}: sku={product_data.get('sku')}, name={product_data.get('name')[:50] if product_data.get('name') else 'N/A'}")
            else:
                logger.warning(f"Товар #{idx+1}: не удалось распарсить (нет обязательных полей)")
                # Выводим структуру элемента для отладки
                if idx < 3:
                    logger.warning(f"  Структура элемента: tag={product_elem.tag}, атрибуты={product_elem.attrib}")
                    for child in product_elem:
                        logger.warning(f"    Дочерний: {child.tag} = {child.text[:50] if child.text else 'None'}")
        
        logger.info(f"Всего распарсено товаров: {len(products_data)}")
        
        if not products_data:
            logger.warning("Товары не найдены в файле после парсинга")
            # Сохраняем информацию о файле для отладки
            logger.warning(f"Размер файла: {file_size} байт")
            logger.warning(f"Корневой элемент XML: {root.tag}")
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
                    # Логируем данные товара перед обработкой (для первых 3)
                    if idx < 3:
                        logger.info(f"Обработка товара #{idx+1}: sku={product_data.get('sku')}, name={product_data.get('name')[:50] if product_data.get('name') else 'N/A'}")
                    
                    product, error, was_created = process_product_from_commerceml(product_data)
                    if product:
                        processed_count += 1
                        if was_created:
                            created_count += 1
                            logger.info(f"✓ Создан товар: {product.article} - {product.name[:50]}")
                        else:
                            updated_count += 1
                            if idx < 10:  # Логируем первые 10 обновлений
                                logger.info(f"✓ Обновлен товар: {product.article} - {product.name[:50]}")
                    elif error:
                        error_info = {
                            'sku': product_data.get('sku', 'unknown'),
                            'error': error
                        }
                        errors.append(error_info)
                        logger.warning(f"✗ Ошибка обработки товара {product_data.get('sku', 'unknown')}: {error}")
                        # Выводим данные товара при ошибке
                        if idx < 5:
                            logger.warning(f"  Данные товара: {product_data}")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"✗ Исключение при обработке товара {product_data.get('sku', 'unknown')}: {error_msg}", exc_info=True)
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


def parse_commerceml_product(product_elem, namespaces, root_elem=None):
    """
    Парсит элемент товара из CommerceML 2 XML.
    
    Возвращает словарь с данными товара в формате, совместимом с validate_product.
    
    Args:
        product_elem: Элемент товара из XML
        namespaces: Словарь с namespace
        root_elem: Корневой элемент XML (опционально, для поиска групп)
    """
    product_data = {}
    
    # Получаем namespace из словаря (если есть)
    namespace = namespaces.get('', namespaces.get('cml', None))
    
    # Функция для поиска элемента с разными вариантами
    def find_elem(tag_name):
        """Ищет элемент с разными вариантами namespace."""
        # Вариант 1: С namespace напрямую (приоритет, если namespace есть)
        if namespace:
            elem = product_elem.find(f'{{{namespace}}}{tag_name}')
            if elem is not None:
                return elem
        
        # Вариант 2: Без namespace (если элементы без namespace)
        elem = product_elem.find(tag_name)
        if elem is not None:
            return elem
        
        # Вариант 3: С префиксом catalog: (только если префикс определен в namespaces)
        # Проверяем, что префикс 'catalog' действительно есть в словаре
        if 'catalog' in namespaces:
            try:
                elem = product_elem.find(f'catalog:{tag_name}', namespaces)
                if elem is not None:
                    return elem
            except (KeyError, ValueError):
                # Если префикс не найден, просто пропускаем
                pass
        
        return None
    
    # Идентификатор товара (Ид)
    id_elem = find_elem('Ид')
    if id_elem is not None and id_elem.text:
        product_data['sku'] = id_elem.text.strip()
        product_data['external_id'] = id_elem.text.strip()
    else:
        # Пробуем найти Ид в атрибутах
        if 'Ид' in product_elem.attrib:
            product_data['sku'] = product_elem.attrib['Ид'].strip()
            product_data['external_id'] = product_elem.attrib['Ид'].strip()
    
    # Артикул
    article_elem = find_elem('Артикул')
    if article_elem is not None and article_elem.text:
        product_data['article'] = article_elem.text.strip()
        if 'sku' not in product_data:
            product_data['sku'] = article_elem.text.strip()
    
    # Наименование
    name_elem = find_elem('Наименование')
    if name_elem is not None and name_elem.text:
        product_data['name'] = name_elem.text.strip()
    
    # Описание
    description_elem = find_elem('Описание')
    if description_elem is not None and description_elem.text:
        product_data['description'] = description_elem.text.strip()
    
    # Цены (ищем в предложениях)
    # В CommerceML цены обычно в отдельном файле предложений, но могут быть и здесь
    price_elem = None
    if namespace:
        price_elem = product_elem.find(f'.//{{{namespace}}}ЦенаЗаЕдиницу')
    if price_elem is None:
        price_elem = product_elem.find('.//ЦенаЗаЕдиницу')
    # Пробуем с префиксом catalog: только если он определен
    if price_elem is None and 'catalog' in namespaces:
        try:
            price_elem = product_elem.find('.//catalog:ЦенаЗаЕдиницу', namespaces)
        except (KeyError, ValueError):
            pass
    if price_elem is not None and price_elem.text:
        try:
            product_data['price'] = float(price_elem.text.strip().replace(',', '.'))
        except (ValueError, AttributeError):
            pass
    
    # Остатки (ищем в предложениях)
    quantity_elem = None
    if namespace:
        quantity_elem = product_elem.find(f'.//{{{namespace}}}Количество')
    if quantity_elem is None:
        quantity_elem = product_elem.find('.//Количество')
    # Пробуем с префиксом catalog: только если он определен
    if quantity_elem is None and 'catalog' in namespaces:
        try:
            quantity_elem = product_elem.find('.//catalog:Количество', namespaces)
        except (KeyError, ValueError):
            pass
    if quantity_elem is not None and quantity_elem.text:
        try:
            product_data['stock'] = int(float(quantity_elem.text.strip().replace(',', '.')))
        except (ValueError, AttributeError):
            pass
    
    # Категория (группа) - ищем название группы
    group_elem = None
    if namespace:
        group_elem = product_elem.find(f'{{{namespace}}}Группы/{{{namespace}}}Ид')
    if group_elem is None:
        group_elem = product_elem.find('Группы/Ид')
    # Пробуем с префиксом catalog: только если он определен
    if group_elem is None and 'catalog' in namespaces:
        try:
            group_elem = product_elem.find('catalog:Группы/catalog:Ид', namespaces)
        except (KeyError, ValueError):
            pass
    if group_elem is not None and group_elem.text:
        product_data['category_id'] = group_elem.text.strip()
        # Пробуем найти название группы в корне документа
        # Используем переданный root_elem
        root = root_elem
        if root is None:
            # Если root не передан, пробуем найти его через итерацию
            # Ищем элемент с namespace КоммерческаяИнформация
            try:
                # Ищем корневой элемент через iter() - он должен быть предком product_elem
                # В ElementTree можно использовать iter() для поиска всех элементов
                # Но проще всего - передавать root из вызывающего кода
                pass  # Если root не передан, просто пропускаем поиск группы
            except:
                pass
        
        if root is not None:
            group_name_elem = None
            if namespace:
                group_name_elem = root.find(f".//{{{namespace}}}Группа[@Ид='{product_data['category_id']}']/{{{namespace}}}Наименование")
            if group_name_elem is None:
                group_name_elem = root.find(f".//Группа[@Ид='{product_data['category_id']}']/Наименование")
            # Пробуем с префиксом catalog: только если он определен
            if group_name_elem is None and 'catalog' in namespaces:
                try:
                    group_name_elem = root.find(f".//catalog:Группа[@Ид='{product_data['category_id']}']/catalog:Наименование", namespaces)
                except (KeyError, ValueError):
                    pass
            if group_name_elem is not None and group_name_elem.text:
                product_data['category_name'] = group_name_elem.text.strip()
    
    # Характеристики товара (ХарактеристикиТовара) - используется в некоторых версиях CommerceML
    characteristics = []
    
    # Вариант 1: ХарактеристикиТовара (как в вашем XML)
    char_elem = None
    if namespace:
        char_elem = product_elem.find(f'{{{namespace}}}ХарактеристикиТовара')
    if char_elem is None:
        char_elem = product_elem.find('ХарактеристикиТовара')
    # Пробуем с префиксом catalog: только если он определен
    if char_elem is None and 'catalog' in namespaces:
        try:
            char_elem = product_elem.find('catalog:ХарактеристикиТовара', namespaces)
        except (KeyError, ValueError):
            pass
    
    if char_elem is not None:
        # Ищем все ХарактеристикаТовара
        char_items = []
        if namespace:
            char_items = char_elem.findall(f'{{{namespace}}}ХарактеристикаТовара')
        if not char_items:
            char_items = char_elem.findall('ХарактеристикаТовара')
        # Пробуем с префиксом catalog: только если он определен
        if not char_items and 'catalog' in namespaces:
            try:
                char_items = char_elem.findall('catalog:ХарактеристикаТовара', namespaces)
            except (KeyError, ValueError):
                pass
        
        for char_item in char_items:
            # Ищем Наименование
            char_name_elem = None
            if namespace:
                char_name_elem = char_item.find(f'{{{namespace}}}Наименование')
            if char_name_elem is None:
                char_name_elem = char_item.find('Наименование')
            # Пробуем с префиксом catalog: только если он определен
            if char_name_elem is None and 'catalog' in namespaces:
                try:
                    char_name_elem = char_item.find('catalog:Наименование', namespaces)
                except (KeyError, ValueError):
                    pass
            
            # Ищем Значение
            char_value_elem = None
            if namespace:
                char_value_elem = char_item.find(f'{{{namespace}}}Значение')
            if char_value_elem is None:
                char_value_elem = char_item.find('Значение')
            # Пробуем с префиксом catalog: только если он определен
            if char_value_elem is None and 'catalog' in namespaces:
                try:
                    char_value_elem = char_item.find('catalog:Значение', namespaces)
                except (KeyError, ValueError):
                    pass
            
            if char_name_elem is not None and char_value_elem is not None:
                char_name = char_name_elem.text.strip() if char_name_elem.text else ''
                char_value = char_value_elem.text.strip() if char_value_elem.text else ''
                
                if char_name and char_value:
                    characteristics.append({
                        'name': char_name,
                        'value': char_value
                    })
                    # Если это марка (бренд), сохраняем отдельно
                    if char_name.lower() in ['марка', 'brand', 'бренд']:
                        product_data['brand'] = char_value
    
    # Вариант 2: ЗначенияСвойств (старый формат)
    if not characteristics:
        props_elem = None
        if namespace:
            props_elem = product_elem.find(f'{{{namespace}}}ЗначенияСвойств')
        if props_elem is None:
            props_elem = product_elem.find('ЗначенияСвойств')
        # Пробуем с префиксом catalog: только если он определен
        if props_elem is None and 'catalog' in namespaces:
            try:
                props_elem = product_elem.find('catalog:ЗначенияСвойств', namespaces)
            except (KeyError, ValueError):
                pass
        
        if props_elem is not None:
            prop_items = []
            if namespace:
                prop_items = props_elem.findall(f'{{{namespace}}}ЗначенияСвойства')
            if not prop_items:
                prop_items = props_elem.findall('ЗначенияСвойства')
            # Пробуем с префиксом catalog: только если он определен
            if not prop_items and 'catalog' in namespaces:
                try:
                    prop_items = props_elem.findall('catalog:ЗначенияСвойства', namespaces)
                except (KeyError, ValueError):
                    pass
            
            for prop_elem in prop_items:
                prop_id = None
                if namespace:
                    prop_id = prop_elem.find(f'{{{namespace}}}Ид')
                if prop_id is None:
                    prop_id = prop_elem.find('Ид')
                # Пробуем с префиксом catalog: только если он определен
                if prop_id is None and 'catalog' in namespaces:
                    try:
                        prop_id = prop_elem.find('catalog:Ид', namespaces)
                    except (KeyError, ValueError):
                        pass
                
                prop_value = None
                if namespace:
                    prop_value = prop_elem.find(f'{{{namespace}}}Значение')
                if prop_value is None:
                    prop_value = prop_elem.find('Значение')
                # Пробуем с префиксом catalog: только если он определен
                if prop_value is None and 'catalog' in namespaces:
                    try:
                        prop_value = prop_elem.find('catalog:Значение', namespaces)
                    except (KeyError, ValueError):
                        pass
                
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
    Использует логику из process_bulk_import для правильной обработки товаров.
    """
    from .services import parse_product_name, get_category_for_product
    from .models import Product, ProductCharacteristic
    
    try:
        # Получаем основные данные
        external_id = product_data.get('external_id') or product_data.get('sku', '')
        name = product_data.get('name', '').strip()
        article = product_data.get('article', '').strip()
        
        if not name:
            return None, "Отсутствует название товара", False
        
        if not external_id and not article:
            return None, "Отсутствует идентификатор товара (Ид или Артикул)", False
        
        # Парсим название для извлечения бренда, артикула и т.д.
        parsed = parse_product_name(name)
        
        # Используем артикул из данных или из парсинга
        if not article and parsed.get('article'):
            article = parsed['article']
        if not article and external_id:
            article = external_id
        
        # Определяем бренд
        brand = product_data.get('brand', '').strip() or parsed.get('brand', '')
        
        # Определяем категорию
        category_name = product_data.get('category_name', '').strip()
        if category_name:
            category = get_category_for_product(category_name)
        else:
            category = get_category_for_product(name)
        
        # Обрабатываем цену
        price = 0
        if 'price' in product_data:
            try:
                price = float(str(product_data['price']).replace(',', '.'))
            except (ValueError, TypeError):
                price = 0
        
        # Обрабатываем остаток
        quantity = 0
        if 'stock' in product_data:
            try:
                quantity = int(float(str(product_data['stock']).replace(',', '.')))
            except (ValueError, TypeError):
                quantity = 0
        
        # Определяем наличие
        availability = 'in_stock' if quantity > 0 else 'out_of_stock'
        
        # Ищем товар по external_id (приоритет) или по артикулу
        product = None
        if external_id:
            product = Product.objects.filter(external_id=external_id, catalog_type='retail').first()
        
        if not product and article:
            product = Product.objects.filter(article=article, catalog_type='retail').first()
        
        was_created = product is None
        
        if was_created:
            # Создаем новый товар
            product = Product(
                external_id=external_id or article,
                article=article,
                name=name,
                brand=brand,
                price=price,
                quantity=quantity,
                availability=availability,
                category=category,
                catalog_type='retail',
                is_active=True
            )
        else:
            # Обновляем существующий товар
            if external_id and not product.external_id:
                product.external_id = external_id
            if article and not product.article:
                product.article = article
            product.name = name
            product.brand = brand
            product.price = price
            product.quantity = quantity
            product.availability = availability
            if category:
                product.category = category
            product.is_active = True
        
        # Описание
        if product_data.get('description'):
            product.description = product_data.get('description')
        
        # Применимость
        if product_data.get('applicability'):
            product.applicability = product_data.get('applicability')
        elif parsed.get('applicability'):
            product.applicability = parsed.get('applicability')
        
        # Кросс-номера
        if product_data.get('cross_numbers'):
            product.cross_numbers = product_data.get('cross_numbers')
        elif parsed.get('oem_number'):
            product.cross_numbers = parsed.get('oem_number')
        
        product.save()
        
        # Обрабатываем характеристики
        if product_data.get('characteristics'):
            # Удаляем старые характеристики
            ProductCharacteristic.objects.filter(product=product).delete()
            
            # Создаем новые
            characteristics = product_data.get('characteristics', [])
            if isinstance(characteristics, list):
                for idx, char_data in enumerate(characteristics):
                    if isinstance(char_data, dict):
                        ProductCharacteristic.objects.create(
                            product=product,
                            name=char_data.get('name', ''),
                            value=char_data.get('value', ''),
                            order=idx
                        )
        
        return product, None, was_created
        
    except Exception as e:
        error_msg = f"Ошибка обработки товара: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg, False
