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
    
    logger.info("=" * 80)
    logger.info(f"НАЧАЛО ОБРАБОТКИ ФАЙЛА COMMERCEML: {filename}")
    logger.info(f"Путь к файлу: {file_path}")
    logger.info(f"Файл существует: {os.path.exists(file_path)}")
    
    try:
        # Проверяем размер файла
        file_size = os.path.getsize(file_path)
        logger.info(f"Размер файла: {file_size} байт")
        logger.info(f"Имя файла (lowercase): {filename.lower()}")
        logger.info(f"Содержит 'import': {'import' in filename.lower()}")
        logger.info(f"Содержит 'offers': {'offers' in filename.lower()}")
        logger.info("=" * 80)
        
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
        
        # Определяем тип каталога (retail или wholesale)
        # Сначала проверяем по имени файла
        filename_lower = filename.lower()
        catalog_type = 'retail'  # По умолчанию розница
        
        # Проверяем различные варианты имен файлов (включая файлы с цифрами)
        # Файлы могут называться: Import0_1.xml, Import1.xml, offers0_1.xml, offers1.xml и т.д.
        if any(keyword in filename_lower for keyword in ['wholesale', 'опт', 'opt', 'wholesale_', '_wholesale', 'партнер', 'partner']):
            catalog_type = 'wholesale'
            logger.info(f"Определен тип каталога: ОПТОВЫЙ (wholesale) по имени файла: {filename}")
        else:
            logger.info(f"Предварительно определен тип каталога: РОЗНИЦА (retail) по имени файла: {filename}")
        
        # Дополнительная проверка: если файл содержит "0_1" или цифры, это может быть оптовый каталог
        # Но по умолчанию оставляем retail, если нет явных указаний
        
        # Ищем каталог товаров или предложения
        # В CommerceML может быть два типа файлов:
        # 1. import.xml, Import0_1.xml, Import1.xml и т.д. - каталог товаров (названия, описания)
        # 2. offers.xml, offers0_1.xml, offers1.xml и т.д. - предложения (цены, остатки)
        
        # Сначала проверяем, не файл ли это предложений
        # Ищем ПакетПредложений или Предложения в корне
        package = None
        if namespace:
            package = root.find(f'.//{{{namespace}}}ПакетПредложений')
        if package is None:
            package = root.find('.//ПакетПредложений')
        if package is None:
            # Пробуем найти Предложения напрямую
            if namespace:
                package = root.find(f'.//{{{namespace}}}Предложения')
            if package is None:
                package = root.find('.//Предложения')
        # Пробуем найти с альтернативными namespace (без префикса catalog)
        if package is None:
            for ns_key in ['cml', 'cml2', '']:
                if ns_key in namespaces:
                    try:
                        ns_value = namespaces[ns_key]
                        if ns_value:
                            package = root.find(f'.//{{{ns_value}}}ПакетПредложений')
                            if package is None:
                                package = root.find(f'.//{{{ns_value}}}Предложения')
                            if package is not None:
                                break
                    except (KeyError, ValueError):
                        pass
        
        logger.info(f"Проверка типа файла: package={package is not None}, filename={filename}")
        logger.info(f"Корневой элемент: {root.tag}, namespace: {namespace or 'нет'}")
        logger.info(f"Дочерние элементы корня: {[child.tag for child in root[:10]]}")
        
        if package is not None:
            # Для файла предложений дополнительно проверяем типы цен
            if catalog_type == 'retail':
                # Ищем типы цен в ПакетПредложений
                price_types_elem = None
                if namespace:
                    price_types_elem = package.find(f'.//{{{namespace}}}ТипыЦен')
                if price_types_elem is None:
                    price_types_elem = package.find('.//ТипыЦен')
                # Пробуем найти с разными вариантами namespace
                if price_types_elem is None:
                    # Пробуем с альтернативными namespace
                    for ns_key in ['cml', 'cml2', '']:
                        if ns_key in namespaces:
                            try:
                                ns_value = namespaces[ns_key]
                                if ns_value:
                                    price_types_elem = package.find(f'.//{{{ns_value}}}ТипыЦен')
                                    if price_types_elem is not None:
                                        break
                            except (KeyError, ValueError):
                                pass
                
                if price_types_elem is not None:
                    # Собираем все элементы ТипЦены
                    price_type_elems = []
                    if namespace:
                        price_type_elems.extend(price_types_elem.findall(f'.//{{{namespace}}}ТипЦены'))
                    price_type_elems.extend(price_types_elem.findall('.//ТипЦены'))
                    # Пробуем с альтернативными namespace
                    for ns_key in ['cml', 'cml2', '']:
                        if ns_key in namespaces:
                            try:
                                ns_value = namespaces[ns_key]
                                if ns_value:
                                    price_type_elems.extend(price_types_elem.findall(f'.//{{{ns_value}}}ТипЦены'))
                            except (KeyError, ValueError, SyntaxError):
                                pass
                    
                    for price_type_elem in price_type_elems:
                        name_elem = None
                        if namespace:
                            name_elem = price_type_elem.find(f'.//{{{namespace}}}Наименование')
                        if name_elem is None:
                            name_elem = price_type_elem.find('.//Наименование')
                        # Пробуем с альтернативными namespace
                        if name_elem is None:
                            for ns_key in ['cml', 'cml2', '']:
                                if ns_key in namespaces:
                                    try:
                                        ns_value = namespaces[ns_key]
                                        if ns_value:
                                            name_elem = price_type_elem.find(f'.//{{{ns_value}}}Наименование')
                                            if name_elem is not None:
                                                break
                                    except (KeyError, ValueError, SyntaxError):
                                        pass
                        if name_elem is not None and name_elem.text:
                            price_type_name = name_elem.text.lower()
                            if any(keyword in price_type_name for keyword in ['опт', 'opt', 'wholesale', 'оптовая', 'оптовый', 'партнер', 'partner']):
                                catalog_type = 'wholesale'
                                logger.info(f"Определен тип каталога: ОПТОВЫЙ (wholesale) по типу цены: {name_elem.text}")
                                break
            
            # ВАЖНО: Файл offers.xml содержит оба типа цен (розничную и оптовую)
            # Нужно обработать его для обоих каталогов, чтобы установить правильные цены
            logger.info(f"Обнаружен файл предложений (offers.xml) - обрабатываем цены и остатки для обоих каталогов")
            
            # Сначала обрабатываем для розничного каталога
            logger.info("=" * 80)
            logger.info("ОБРАБОТКА ДЛЯ РОЗНИЧНОГО КАТАЛОГА (retail)")
            logger.info("=" * 80)
            result_retail = process_offers_file(root, namespaces, filename, request, catalog_type='retail')
            
            # Затем обрабатываем для оптового каталога
            logger.info("=" * 80)
            logger.info("ОБРАБОТКА ДЛЯ ОПТОВОГО КАТАЛОГА (wholesale)")
            logger.info("=" * 80)
            result_wholesale = process_offers_file(root, namespaces, filename, request, catalog_type='wholesale')
            
            # Объединяем результаты
            return {
                'status': 'success' if result_retail.get('status') == 'success' and result_wholesale.get('status') == 'success' else 'partial',
                'processed': result_retail.get('processed', 0) + result_wholesale.get('processed', 0),
                'updated': result_retail.get('updated', 0) + result_wholesale.get('updated', 0),
                'errors': result_retail.get('errors', []) + result_wholesale.get('errors', [])
            }
        
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
        
        # Дополнительная проверка: если тип еще не определен как опт, проверяем название каталога
        if catalog_type == 'retail':
            catalog_name_elem = None
            if namespace:
                catalog_name_elem = catalog.find(f'.//{{{namespace}}}Наименование')
            if catalog_name_elem is None:
                catalog_name_elem = catalog.find('.//Наименование')
            if catalog_name_elem is None and 'catalog' in namespaces:
                try:
                    catalog_name_elem = catalog.find('.//catalog:Наименование', namespaces)
                except (KeyError, ValueError):
                    pass
            
            if catalog_name_elem is not None and catalog_name_elem.text:
                catalog_name = catalog_name_elem.text.lower()
                if any(keyword in catalog_name for keyword in ['опт', 'opt', 'wholesale', 'оптовый', 'оптовая', 'партнер', 'partner']):
                    catalog_type = 'wholesale'
                    logger.info(f"Определен тип каталога: ОПТОВЫЙ (wholesale) по названию каталога: {catalog_name_elem.text}")
                else:
                    logger.info(f"Тип каталога подтвержден как РОЗНИЦА (retail) по названию каталога: {catalog_name_elem.text}")
        
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
            # Если это файл каталога (import.xml), но товары не найдены - это ошибка
            # Создаем SyncLog с предупреждением
            request_ip = get_client_ip(request) if request else None
            SyncLog.objects.create(
                operation_type='file_upload',
                status='partial',
                message=f'Файл {filename} обработан, но товары не найдены в XML',
                processed_count=0,
                created_count=0,
                updated_count=0,
                errors_count=1,
                errors=[{'error': 'Товары не найдены в XML файле. Проверьте структуру файла.'}],
                request_ip=request_ip,
                request_format='CommerceML 2',
                filename=filename,
                processing_time=0
            )
            return {'status': 'partial', 'message': 'Товары не найдены в файле', 'processed': 0, 'created': 0, 'updated': 0}
        
        # ВАЖНО: Файл import.xml содержит товары для обоих каталогов (розничного и оптового)
        # Нужно обработать его для обоих каталогов, чтобы создать товары в обоих разделах
        logger.info(f"Обнаружен файл каталога товаров (import.xml) - обрабатываем товары для обоих каталогов")
        
        # Обрабатываем для обоих каталогов
        results = {}
        total_processed = 0
        total_created = 0
        total_updated = 0
        total_deleted = 0
        all_errors = []
        
        for current_catalog_type in ['retail', 'wholesale']:
            logger.info("=" * 80)
            logger.info(f"ОБРАБОТКА ДЛЯ КАТАЛОГА: {current_catalog_type.upper()}")
            logger.info("=" * 80)
            
            # Обрабатываем товары - каждый в отдельной транзакции
            # Это позволяет избежать ситуации, когда ошибка одного товара ломает обработку всех остальных
            processed_count = 0
            created_count = 0
            updated_count = 0
            errors = []
            
            logger.info(f"Начало обработки {len(products_data)} товаров для каталога {current_catalog_type} (каждый в отдельной транзакции)")
            
            for idx, product_data in enumerate(products_data):
                # Каждый товар обрабатывается в отдельной транзакции
                # Это гарантирует, что ошибка одного товара не повлияет на обработку остальных
                try:
                    with transaction.atomic():
                        # Логируем данные товара перед обработкой (для первых 3)
                        if idx < 3:
                            logger.info(f"Обработка товара #{idx+1} для {current_catalog_type}: sku={product_data.get('sku')}, name={product_data.get('name')[:50] if product_data.get('name') else 'N/A'}")
                        
                        product, error, was_created = process_product_from_commerceml(product_data, catalog_type=current_catalog_type)
                        if product:
                            processed_count += 1
                            if was_created:
                                created_count += 1
                                logger.info(f"✓ Создан товар в каталоге {current_catalog_type}: {product.article} - {product.name[:50]}")
                            else:
                                updated_count += 1
                                if idx < 10:  # Логируем первые 10 обновлений
                                    logger.info(f"✓ Обновлен товар в каталоге {current_catalog_type}: {product.article} - {product.name[:50]}")
                        elif error:
                            # Ошибка внутри process_product_from_commerceml
                            error_info = {
                                'sku': product_data.get('sku', 'unknown'),
                                'catalog_type': current_catalog_type,
                                'error': error
                            }
                            errors.append(error_info)
                            logger.warning(f"✗ Ошибка обработки товара {product_data.get('sku', 'unknown')} для {current_catalog_type}: {error}")
                            # Выводим данные товара при ошибке (только для первых 5)
                            if idx < 5:
                                logger.warning(f"  Данные товара: {product_data}")
                except Exception as e:
                    # Исключение при обработке товара - транзакция автоматически откатывается
                    error_msg = str(e)
                    logger.error(f"✗ Исключение при обработке товара {product_data.get('sku', 'unknown')} для {current_catalog_type}: {error_msg}", exc_info=True)
                    errors.append({
                        'sku': product_data.get('sku', 'unknown'),
                        'catalog_type': current_catalog_type,
                        'error': error_msg
                    })
                    # Выводим данные товара при ошибке (только для первых 5)
                    if idx < 5:
                        logger.warning(f"  Данные товара: {product_data}")
                    # Транзакция автоматически откатывается при исключении
                    # Продолжаем обработку следующего товара
            
            logger.info(f"Обработка для {current_catalog_type} завершена: обработано={processed_count}, создано={created_count}, обновлено={updated_count}, ошибок={len(errors)}")
            
            # ВАЖНО: Скрываем товары, которые были импортированы из 1С, но не пришли в текущем обмене
            # Это означает, что они были удалены в 1С
            # Собираем все external_id из обработанных товаров (это уникальный идентификатор из 1С)
            processed_external_ids = set()
            
            for product_data in products_data:
                external_id = product_data.get('external_id') or product_data.get('sku')
                if external_id:
                    processed_external_ids.add(str(external_id).strip())
            
            logger.info(f"Обработано товаров в обмене: {len(processed_external_ids)} с external_id для каталога {current_catalog_type}")
            
            # Находим товары, которые были импортированы из 1С (имеют external_id),
            # но не пришли в текущем обмене
            # ВАЖНО: Скрываем только товары из того же типа каталога (retail или wholesale)
            deleted_count = 0
            if processed_external_ids:
                # Ищем товары, которые:
                # 1. Имеют external_id (были импортированы из 1С)
                # 2. Принадлежат к текущему типу каталога (retail или wholesale)
                # 3. Были активны (чтобы не трогать уже скрытые)
                # 4. Их external_id нет в списке обработанных
                products_to_hide = Product.objects.filter(
                    catalog_type=current_catalog_type,  # Только товары из текущего типа каталога
                    is_active=True,
                    external_id__isnull=False,
                    external_id__gt=''  # Не пустой
                ).exclude(external_id__in=processed_external_ids)
                
                deleted_count = products_to_hide.count()
                if deleted_count > 0:
                    logger.info(f"Найдено {deleted_count} товаров в каталоге {current_catalog_type}, которые не пришли в обмене - скрываем их (удалены в 1С)")
                    # Логируем первые 5 для отладки
                    for product in products_to_hide[:5]:
                        logger.info(f"  Скрываем: {product.name[:50]} (external_id={product.external_id}, article={product.article})")
                    
                    # Скрываем товары (не удаляем физически, чтобы сохранить историю)
                    products_to_hide.update(is_active=False, availability='out_of_stock', quantity=0)
                    logger.info(f"✓ Скрыто товаров в каталоге {current_catalog_type}: {deleted_count}")
                else:
                    logger.info(f"Все товары из 1С присутствуют в обмене для каталога {current_catalog_type}, скрывать нечего")
            else:
                logger.warning(f"⚠ В обмене нет товаров с external_id для каталога {current_catalog_type} - невозможно определить удаленные товары")
            
            # Сохраняем результаты для текущего каталога
            results[current_catalog_type] = {
                'processed': processed_count,
                'created': created_count,
                'updated': updated_count,
                'deleted': deleted_count,
                'errors': errors
            }
            
            # Суммируем общие результаты
            total_processed += processed_count
            total_created += created_count
            total_updated += updated_count
            total_deleted += deleted_count
            all_errors.extend(errors)
        
        # Создаем лог синхронизации
        processing_time = (timezone.now() - start_time).total_seconds()
        
        request_ip = get_client_ip(request) if request else None
        
        # ВАЖНО: Статус 'success' только если товары действительно обработаны
        # Если processed_count = 0, это ошибка, а не успех
        if total_processed == 0:
            status = 'failure'
            message = f'Файл {filename} обработан, но товары не были созданы или обновлены'
        elif all_errors:
            status = 'partial'
            message = f'Обработано товаров из файла {filename} для обоих каталогов (с ошибками)'
        else:
            status = 'success'
            message = f'Обработано товаров из файла {filename} для обоих каталогов'
        
        sync_log = SyncLog.objects.create(
            operation_type='file_upload',
            status=status,
            message=message,
            processed_count=total_processed,
            created_count=total_created,
            updated_count=total_updated,
            errors_count=len(all_errors),
            errors=all_errors,
            request_ip=request_ip,
            request_format='CommerceML 2',
            filename=filename,
            processing_time=processing_time
        )
        
        logger.info(f"Импорт завершен: обработано {total_processed}, создано {total_created}, обновлено {total_updated}, скрыто {total_deleted}, ошибок {len(all_errors)}")
        logger.info(f"  Розничный каталог: обработано={results['retail']['processed']}, создано={results['retail']['created']}, обновлено={results['retail']['updated']}")
        logger.info(f"  Оптовый каталог: обработано={results['wholesale']['processed']}, создано={results['wholesale']['created']}, обновлено={results['wholesale']['updated']}")
        
        return {
            'status': 'success',
            'processed': total_processed,
            'created': total_created,
            'updated': total_updated,
            'deleted': total_deleted,
            'errors': len(all_errors),
            'retail': results['retail'],
            'wholesale': results['wholesale']
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
    import re  # Импортируем re в начале функции
    
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
        # Логируем для диагностики (только первые 3 товара)
        if not hasattr(parse_commerceml_product, '_log_count'):
            parse_commerceml_product._log_count = 0
        parse_commerceml_product._log_count += 1
        if parse_commerceml_product._log_count <= 3:
            logger.info(f"Найден Ид товара в XML: {product_data['external_id']}")
    else:
        # Пробуем найти Ид в атрибутах
        if 'Ид' in product_elem.attrib:
            product_data['sku'] = product_elem.attrib['Ид'].strip()
            product_data['external_id'] = product_elem.attrib['Ид'].strip()
            # Логируем для диагностики
            if not hasattr(parse_commerceml_product, '_log_count'):
                parse_commerceml_product._log_count = 0
            parse_commerceml_product._log_count += 1
            if parse_commerceml_product._log_count <= 3:
                logger.info(f"Найден Ид товара в атрибутах XML: {product_data['external_id']}")
        else:
            # Логируем, если Ид не найден (только первые 3 товара)
            if not hasattr(parse_commerceml_product, '_log_count'):
                parse_commerceml_product._log_count = 0
            parse_commerceml_product._log_count += 1
            if parse_commerceml_product._log_count <= 3:
                logger.warning(f"⚠ Ид товара не найден в XML! Тег товара: {product_elem.tag}, атрибуты: {product_elem.attrib}")
    
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
    # Ищем цену в разных возможных местах структуры XML
    price_elem = None
    if namespace:
        # Вариант 1: ЦенаЗаЕдиницу напрямую
        price_elem = product_elem.find(f'.//{{{namespace}}}ЦенаЗаЕдиницу')
        # Вариант 2: Цены/Цена/ЦенаЗаЕдиницу (полная структура)
        if price_elem is None:
            price_elem = product_elem.find(f'.//{{{namespace}}}Цены/{{{namespace}}}Цена/{{{namespace}}}ЦенаЗаЕдиницу')
        # Вариант 3: Предложения/Предложение/Цены/Цена/ЦенаЗаЕдиницу
        if price_elem is None:
            price_elem = product_elem.find(f'.//{{{namespace}}}Предложения/{{{namespace}}}Предложение/{{{namespace}}}Цены/{{{namespace}}}Цена/{{{namespace}}}ЦенаЗаЕдиницу')
    if price_elem is None:
        # Без namespace
        price_elem = product_elem.find('.//ЦенаЗаЕдиницу')
        if price_elem is None:
            price_elem = product_elem.find('.//Цены/Цена/ЦенаЗаЕдиницу')
        if price_elem is None:
            price_elem = product_elem.find('.//Предложения/Предложение/Цены/Цена/ЦенаЗаЕдиницу')
    # Пробуем с префиксом catalog: только если он определен
    if price_elem is None and 'catalog' in namespaces:
        try:
            price_elem = product_elem.find('.//catalog:ЦенаЗаЕдиницу', namespaces)
            if price_elem is None:
                price_elem = product_elem.find('.//catalog:Цены/catalog:Цена/catalog:ЦенаЗаЕдиницу', namespaces)
        except (KeyError, ValueError):
            pass
    
    if price_elem is not None and price_elem.text:
        try:
            price_str = price_elem.text.strip().replace(',', '.').replace(' ', '').replace('\xa0', '')
            if price_str:
                product_data['price'] = float(price_str)
        except (ValueError, AttributeError, TypeError):
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
                    char_name_lower = char_name.lower()
                    
                    # Обрабатываем служебные характеристики - они не должны попадать в characteristics
                    # Артикул1 → article (кросс-номер)
                    if char_name_lower in ['артикул1', 'артикул 1', 'article1', 'article 1']:
                        if not product_data.get('article'):
                            product_data['article'] = char_value
                        # Добавляем в кросс-номера, если article уже был заполнен
                        elif product_data.get('article') != char_value:
                            if 'cross_numbers' not in product_data:
                                product_data['cross_numbers'] = []
                            product_data['cross_numbers'].append(char_value)
                    
                    # Артикул2 → cross_numbers (OEM номер)
                    elif char_name_lower in ['артикул2', 'артикул 2', 'article2', 'article 2', 'oem', 'oem номер']:
                        if 'cross_numbers' not in product_data:
                            product_data['cross_numbers'] = []
                        product_data['cross_numbers'].append(char_value)
                    
                    # Марка → brand (бренд)
                    elif char_name_lower in ['марка', 'brand', 'бренд']:
                        product_data['brand'] = char_value
                    
                    # Двигатель → applicability (применимость)
                    elif char_name_lower in ['двигатель', 'engine', 'мотор']:
                        if 'applicability' not in product_data:
                            product_data['applicability'] = []
                        product_data['applicability'].append(char_value)
                    
                    # Все остальные характеристики добавляем в список
                    # ВАЖНО: Фильтруем неправильные значения (коды моделей, материалы и т.д.)
                    else:
                        # Исключаем материалы
                        excluded_materials = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
                        char_name_lower = char_name.lower()
                        char_value_upper = char_value.upper()
                        
                        # Пропускаем материалы
                        if any(material in char_name_lower for material in excluded_materials):
                            continue
                        
                        # Если это размер, проверяем, что это действительно размер
                        if 'размер' in char_name_lower or 'size' in char_name_lower:
                            # Размер должен содержать числа и * или x (например, 20*450)
                            if not re.search(r'\d+[*x]\d+', char_value):
                                # Это не размер, пропускаем
                                continue
                        
                        # Проверяем, что значение не является кодом модели/применимости
                        # Коды моделей обычно: 1-4 цифры + буквы (например, 1GEN, 1NZF, 2GR, 4AFE)
                        # Или только буквы+цифры без * или x
                        if re.match(r'^[A-Z0-9#\-/]{1,10}$', char_value_upper) and not re.search(r'[*x]', char_value):
                            # Это похоже на код модели, а не на характеристику - пропускаем
                            continue
                        
                        characteristics.append({
                            'name': char_name,
                            'value': char_value
                        })
    
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
    
    # Активность - по умолчанию товар активен (будет обновлено при обработке остатков)
    product_data['is_active'] = True
    
    return product_data if product_data.get('sku') and product_data.get('name') else None


def process_offers_file(root, namespaces, filename, request=None, catalog_type='retail'):
    """
    Обрабатывает файл предложений (offers.xml) - обновляет цены и остатки.
    
    Args:
        root: Корневой элемент XML
        namespaces: Словарь с namespace
        filename: Имя файла
        request: Объект запроса Django
        catalog_type: Тип каталога ('retail' или 'wholesale')
    """
    logger.info(f"Обработка файла предложений (offers.xml) для каталога: {catalog_type}")
    
    start_time = timezone.now()
    processed_count = 0
    updated_count = 0
    errors = []
    
    # Получаем namespace из словаря
    namespace = namespaces.get('', namespaces.get('cml', namespaces.get('cml2', None)))
    
    # Ищем предложения с учетом namespace
    offers = []
    if namespace:
        # Вариант 1: С namespace напрямую
        offers = root.findall(f'.//{{{namespace}}}Предложение')
        # Вариант 2: В ПакетПредложений/Предложения/Предложение
        if not offers:
            package = root.find(f'.//{{{namespace}}}ПакетПредложений')
            if package is not None:
                offers = package.findall(f'.//{{{namespace}}}Предложение')
    if not offers:
        # Вариант 3: Без namespace
        offers = root.findall('.//Предложение')
        if not offers:
            package = root.find('.//ПакетПредложений')
            if package is not None:
                offers = package.findall('.//Предложение')
    if not offers and 'catalog' in namespaces:
        # Вариант 4: С префиксом catalog:
        try:
            offers = root.findall('.//catalog:Предложение', namespaces)
            if not offers:
                package = root.find('.//catalog:ПакетПредложений', namespaces)
                if package is not None:
                    offers = package.findall('.//catalog:Предложение', namespaces)
        except (KeyError, ValueError):
            pass
    
    logger.info(f"Найдено предложений: {len(offers)}")
    logger.info(f"Обработка для каталога: {catalog_type}")
    
    # Проверяем, сколько товаров уже есть в базе для этого каталога
    existing_products_count = Product.objects.filter(catalog_type=catalog_type).count()
    logger.info(f"Товаров в базе для каталога {catalog_type}: {existing_products_count}")
    
    # Проверяем, сколько товаров есть во всех каталогах
    all_products_count = Product.objects.count()
    logger.info(f"Всего товаров в базе: {all_products_count}")
    
    if not offers:
        logger.warning("Предложения не найдены в файле offers.xml")
        return {'status': 'success', 'message': 'Предложения не найдены в файле'}
    
    # Обрабатываем каждое предложение в отдельной транзакции
    # Это позволяет избежать ситуации, когда ошибка одного предложения ломает обработку всех остальных
    logger.info(f"Начало обработки {len(offers)} предложений (каждое в отдельной транзакции)")
    
    for idx, offer_elem in enumerate(offers):
        # Каждое предложение обрабатывается в отдельной транзакции
        try:
            with transaction.atomic():
                # Ищем Ид товара
                product_id_elem = None
                if namespace:
                    product_id_elem = offer_elem.find(f'{{{namespace}}}Ид')
                if product_id_elem is None:
                    product_id_elem = offer_elem.find('.//Ид')
                if product_id_elem is None and 'catalog' in namespaces:
                    try:
                        product_id_elem = offer_elem.find('catalog:Ид', namespaces)
                    except (KeyError, ValueError):
                        pass
                
                if product_id_elem is None or not product_id_elem.text:
                    if idx < 5:
                        logger.warning(f"Предложение #{idx+1}: не найден Ид товара")
                    continue
                
                product_id = product_id_elem.text.strip()
                
                # Ищем товар по external_id сначала в нужном типе каталога, потом в любом
                product = Product.objects.filter(external_id=product_id, catalog_type=catalog_type).first()
                if not product:
                    # Пробуем по артикулу в нужном типе каталога
                    product = Product.objects.filter(article=product_id, catalog_type=catalog_type).first()
                
                # Если не нашли в нужном типе каталога, ищем в любом каталоге
                if not product:
                    product = Product.objects.filter(external_id=product_id).first()
                if not product:
                    product = Product.objects.filter(article=product_id).first()
                
                # Если товар найден, но в другом каталоге, создаем копию в нужном каталоге
                if product and product.catalog_type != catalog_type:
                    # Создаем товар в нужном каталоге на основе найденного
                    existing_product = product
                    product = Product.objects.filter(
                        external_id=product_id,
                        catalog_type=catalog_type
                    ).first()
                    if not product:
                        product = Product.objects.filter(
                            article=product_id,
                            catalog_type=catalog_type
                        ).first()
                    
                    if not product:
                        # Создаем новый товар в нужном каталоге
                        # external_id должен быть уникальным, поэтому используем его только если он есть
                        product_external_id = existing_product.external_id.strip() if existing_product.external_id and existing_product.external_id.strip() else None
                        product = Product(
                            external_id=product_external_id,
                            article=existing_product.article or '',
                            name=existing_product.name or '',
                            brand=existing_product.brand or '',
                            category=existing_product.category,
                            description=existing_product.description or '',
                            short_description=existing_product.short_description or '',
                            applicability=existing_product.applicability or '',
                            cross_numbers=existing_product.cross_numbers or '',
                            characteristics=existing_product.characteristics or '',
                            farpost_url=existing_product.farpost_url or '',
                            condition=existing_product.condition or 'new',
                            catalog_type=catalog_type,
                            is_active=False,  # Будет активирован после обновления цены/остатка
                        )
                        # Устанавливаем цену в зависимости от типа каталога
                        if catalog_type == 'wholesale':
                            product.wholesale_price = existing_product.wholesale_price or existing_product.price
                            product.price = existing_product.price
                        else:
                            product.price = existing_product.price
                            product.wholesale_price = existing_product.wholesale_price
                        product.save()
                        if idx < 5:
                            logger.info(f"Создан товар в каталоге {catalog_type} на основе товара из другого каталога: {product_id}")
                
                if not product:
                    # Товар не найден - логируем для отладки
                    if idx < 50:  # Увеличиваем количество логируемых предупреждений для диагностики
                        logger.warning(f"⚠ Товар с Ид {product_id} не найден в базе (catalog_type={catalog_type}). Проверяем, есть ли товары с таким external_id в других каталогах...")
                        # Проверяем, есть ли товар с таким external_id в любом каталоге
                        any_product = Product.objects.filter(external_id=product_id).first()
                        if any_product:
                            logger.warning(f"  → Найден товар в каталоге {any_product.catalog_type}, но нужен {catalog_type}. Создаем копию...")
                                # Создаем копию товара в нужном каталоге
                            # external_id должен быть уникальным, поэтому используем его только если он есть
                            product_external_id = any_product.external_id.strip() if any_product.external_id and any_product.external_id.strip() else None
                            product = Product(
                                external_id=product_external_id,
                                article=any_product.article or '',
                                name=any_product.name or '',
                                brand=any_product.brand or '',
                                category=any_product.category,
                                description=any_product.description or '',
                                short_description=any_product.short_description or '',
                                applicability=any_product.applicability or '',
                                cross_numbers=any_product.cross_numbers or '',
                                characteristics=any_product.characteristics or '',
                                farpost_url=any_product.farpost_url or '',
                                condition=any_product.condition or 'new',
                                catalog_type=catalog_type,
                                is_active=False,  # Будет активирован после обновления цены/остатка
                            )
                            # Устанавливаем цену в зависимости от типа каталога
                            if catalog_type == 'wholesale':
                                product.wholesale_price = any_product.wholesale_price or any_product.price
                                product.price = any_product.price
                            else:
                                product.price = any_product.price
                                product.wholesale_price = any_product.wholesale_price
                            product.save()
                            logger.info(f"  ✓ Создан товар в каталоге {catalog_type} на основе товара из каталога {any_product.catalog_type}")
                        else:
                            any_product = Product.objects.filter(article=product_id).first()
                            if any_product:
                                logger.warning(f"  → Найден товар по артикулу в каталоге {any_product.catalog_type}, но нужен {catalog_type}. Создаем копию...")
                                # Создаем копию товара в нужном каталоге
                                # external_id должен быть уникальным, поэтому используем его только если он есть
                                product_external_id = None
                                if any_product.external_id and any_product.external_id.strip():
                                    product_external_id = any_product.external_id.strip()
                                elif product_id and product_id.strip():
                                    product_external_id = product_id.strip()
                                product = Product(
                                    external_id=product_external_id,
                                    article=any_product.article or '',
                                    name=any_product.name or '',
                                    brand=any_product.brand or '',
                                    category=any_product.category,
                                    description=any_product.description or '',
                                    short_description=any_product.short_description or '',
                                    applicability=any_product.applicability or '',
                                    cross_numbers=any_product.cross_numbers or '',
                                    characteristics=any_product.characteristics or '',
                                    farpost_url=any_product.farpost_url or '',
                                    condition=any_product.condition or 'new',
                                    catalog_type=catalog_type,
                                    is_active=False,  # Будет активирован после обновления цены/остатка
                                )
                                # Устанавливаем цену в зависимости от типа каталога
                                if catalog_type == 'wholesale':
                                    product.wholesale_price = any_product.wholesale_price or any_product.price
                                    product.price = any_product.price
                                else:
                                    product.price = any_product.price
                                    product.wholesale_price = any_product.wholesale_price
                                product.save()
                                logger.info(f"  ✓ Создан товар в каталоге {catalog_type} на основе товара из каталога {any_product.catalog_type}")
                            else:
                                logger.warning(f"  → Товар не найден ни в одном каталоге. Убедитесь, что import.xml обработан перед offers.xml")
                                # Пропускаем этот товар - он должен быть создан из import.xml
                                continue
                    else:
                        # Пропускаем этот товар - он должен быть создан из import.xml
                        continue
                
                # Обновляем цену из предложений (приоритет - цены из offers.xml)
                # В offers.xml может быть несколько типов цен:
                # f6708032-0bd5-11f1-811f-00155d01d802 - розничная цена
                # b12f44c0-1208-11f1-811f-00155d01d802 - оптовая цена
                
                # Определяем ID типов цен
                RETAIL_PRICE_TYPE_ID = 'f6708032-0bd5-11f1-811f-00155d01d802'
                WHOLESALE_PRICE_TYPE_ID = 'b12f44c0-1208-11f1-811f-00155d01d802'
                
                # Ищем все цены в предложении
                prices_elem = None
                if namespace:
                    prices_elem = offer_elem.find(f'.//{{{namespace}}}Цены')
                if prices_elem is None:
                    prices_elem = offer_elem.find('.//Цены')
                if prices_elem is None and 'catalog' in namespaces:
                    try:
                        prices_elem = offer_elem.find('.//catalog:Цены', namespaces)
                    except (KeyError, ValueError):
                        pass
                
                price = None
                if prices_elem is not None:
                    # Ищем все элементы Цена
                    price_elems = []
                    if namespace:
                        price_elems = prices_elem.findall(f'{{{namespace}}}Цена')
                    if not price_elems:
                        price_elems = prices_elem.findall('Цена')
                    if not price_elems and 'catalog' in namespaces:
                        try:
                            price_elems = prices_elem.findall('catalog:Цена', namespaces)
                        except (KeyError, ValueError):
                            pass
                    
                    # Ищем нужную цену по типу каталога
                    for price_elem in price_elems:
                        # Ищем ИдТипаЦены
                        price_type_id_elem = None
                        if namespace:
                            price_type_id_elem = price_elem.find(f'{{{namespace}}}ИдТипаЦены')
                        if price_type_id_elem is None:
                            price_type_id_elem = price_elem.find('ИдТипаЦены')
                        if price_type_id_elem is None and 'catalog' in namespaces:
                            try:
                                price_type_id_elem = price_elem.find('catalog:ИдТипаЦены', namespaces)
                            except (KeyError, ValueError):
                                pass
                        
                        if price_type_id_elem is not None and price_type_id_elem.text:
                            price_type_id = price_type_id_elem.text.strip()
                            
                            # Проверяем, подходит ли эта цена для текущего типа каталога
                            is_correct_price_type = False
                            if catalog_type == 'wholesale':
                                # Для оптового каталога нужна оптовая цена
                                is_correct_price_type = (price_type_id == WHOLESALE_PRICE_TYPE_ID)
                            else:
                                # Для розничного каталога нужна розничная цена
                                is_correct_price_type = (price_type_id == RETAIL_PRICE_TYPE_ID)
                            
                            if is_correct_price_type:
                                # Ищем ЦенаЗаЕдиницу
                                price_value_elem = None
                                if namespace:
                                    price_value_elem = price_elem.find(f'{{{namespace}}}ЦенаЗаЕдиницу')
                                if price_value_elem is None:
                                    price_value_elem = price_elem.find('ЦенаЗаЕдиницу')
                                if price_value_elem is None and 'catalog' in namespaces:
                                    try:
                                        price_value_elem = price_elem.find('catalog:ЦенаЗаЕдиницу', namespaces)
                                    except (KeyError, ValueError):
                                        pass
                                
                                if price_value_elem is not None and price_value_elem.text:
                                    try:
                                        price_str = price_value_elem.text.strip().replace(',', '.').replace(' ', '').replace('\xa0', '')
                                        if price_str:
                                            price = float(price_str)
                                            if price > 0:
                                                # Для оптового каталога обновляем wholesale_price, для розничного - price
                                                if catalog_type == 'wholesale':
                                                    product.wholesale_price = price
                                                    if idx < 10:
                                                        logger.info(f"✓ Обновлена оптовая цена для товара {product_id}: {price} (тип цены: {price_type_id})")
                                                else:
                                                    product.price = price
                                                    if idx < 10:
                                                        logger.info(f"✓ Обновлена розничная цена для товара {product_id}: {price} (тип цены: {price_type_id})")
                                                break  # Нашли нужную цену, выходим из цикла
                                    except (ValueError, AttributeError, TypeError) as e:
                                        if idx < 5:
                                            logger.warning(f"Не удалось распарсить цену для товара {product_id}: {price_value_elem.text}, ошибка: {e}")
                
                # Если не нашли цену по типу, пробуем взять нужную цену (fallback)
                # ВАЖНО: Для оптового каталога ищем оптовую цену, для розничного - розничную
                if price is None or price == 0:
                    if prices_elem is not None:
                        price_elems = []
                        if namespace:
                            price_elems = prices_elem.findall(f'{{{namespace}}}Цена')
                        if not price_elems:
                            price_elems = prices_elem.findall('Цена')
                        if not price_elems and 'catalog' in namespaces:
                            try:
                                price_elems = prices_elem.findall('catalog:Цена', namespaces)
                            except (KeyError, ValueError):
                                pass
                        
                        # Сначала пытаемся найти нужный тип цены (оптовая для оптового каталога, розничная для розничного)
                        for price_elem in price_elems:
                            price_type_id_elem = None
                            if namespace:
                                price_type_id_elem = price_elem.find(f'{{{namespace}}}ИдТипаЦены')
                            if price_type_id_elem is None:
                                price_type_id_elem = price_elem.find('ИдТипаЦены')
                            if price_type_id_elem is None and 'catalog' in namespaces:
                                try:
                                    price_type_id_elem = price_elem.find('catalog:ИдТипаЦены', namespaces)
                                except (KeyError, ValueError):
                                    pass
                            
                            if price_type_id_elem is not None and price_type_id_elem.text:
                                price_type_id = price_type_id_elem.text.strip()
                                # Проверяем, подходит ли эта цена для текущего типа каталога
                                is_correct_price_type = False
                                if catalog_type == 'wholesale':
                                    is_correct_price_type = (price_type_id == WHOLESALE_PRICE_TYPE_ID)
                                else:
                                    is_correct_price_type = (price_type_id == RETAIL_PRICE_TYPE_ID)
                                
                                if is_correct_price_type:
                                    price_value_elem = None
                                    if namespace:
                                        price_value_elem = price_elem.find(f'{{{namespace}}}ЦенаЗаЕдиницу')
                                    if price_value_elem is None:
                                        price_value_elem = price_elem.find('ЦенаЗаЕдиницу')
                                    if price_value_elem is None and 'catalog' in namespaces:
                                        try:
                                            price_value_elem = price_elem.find('catalog:ЦенаЗаЕдиницу', namespaces)
                                        except (KeyError, ValueError):
                                            pass
                                    
                                    if price_value_elem is not None and price_value_elem.text:
                                        try:
                                            price_str = price_value_elem.text.strip().replace(',', '.').replace(' ', '').replace('\xa0', '')
                                            if price_str:
                                                price = float(price_str)
                                                if price > 0:
                                                    # Для оптового каталога обновляем wholesale_price, для розничного - price
                                                    if catalog_type == 'wholesale':
                                                        product.wholesale_price = price
                                                        if idx < 5:
                                                            logger.info(f"Обновлена оптовая цена (fallback по типу) для товара {product_id}: {price}")
                                                    else:
                                                        product.price = price
                                                        if idx < 5:
                                                            logger.info(f"Обновлена розничная цена (fallback по типу) для товара {product_id}: {price}")
                                                    break
                                        except (ValueError, AttributeError, TypeError):
                                            pass
                        
                        # Если все еще не нашли, берем первую ненулевую цену (последний fallback)
                        if (price is None or price == 0) and catalog_type == 'wholesale':
                            # Для оптового каталога в крайнем случае берем любую цену, но логируем
                            for price_elem in price_elems:
                                price_value_elem = None
                                if namespace:
                                    price_value_elem = price_elem.find(f'{{{namespace}}}ЦенаЗаЕдиницу')
                                if price_value_elem is None:
                                    price_value_elem = price_elem.find('ЦенаЗаЕдиницу')
                                if price_value_elem is None and 'catalog' in namespaces:
                                    try:
                                        price_value_elem = price_elem.find('catalog:ЦенаЗаЕдиницу', namespaces)
                                    except (KeyError, ValueError):
                                        pass
                                
                                if price_value_elem is not None and price_value_elem.text:
                                    try:
                                        price_str = price_value_elem.text.strip().replace(',', '.').replace(' ', '').replace('\xa0', '')
                                        if price_str:
                                            price = float(price_str)
                                            if price > 0:
                                                product.wholesale_price = price
                                                if idx < 5:
                                                    logger.warning(f"⚠ Обновлена оптовая цена (fallback - любая цена) для товара {product_id}: {price}")
                                                break
                                    except (ValueError, AttributeError, TypeError):
                                        pass
                
                # Обновляем остаток
                # Количество может быть в:
                # 1. <Количество>268</Количество>
                # 2. <Склад КоличествоНаСкладе="268"/>
                quantity = None
                quantity_elem = None
                
                # Вариант 1: Ищем элемент <Количество> (используем findall для поиска всех вложенных элементов)
                quantity_elems = []
                if namespace:
                    quantity_elems = offer_elem.findall(f'.//{{{namespace}}}Количество')
                if not quantity_elems:
                    quantity_elems = offer_elem.findall('.//Количество')
                if not quantity_elems and 'catalog' in namespaces:
                    try:
                        quantity_elems = offer_elem.findall('.//catalog:Количество', namespaces)
                    except (KeyError, ValueError):
                        pass
                
                # Берем первый найденный элемент с количеством
                if quantity_elems:
                    quantity_elem = quantity_elems[0]
                
                if quantity_elem is not None and quantity_elem.text:
                    try:
                        quantity = int(float(quantity_elem.text.strip().replace(',', '.')))
                        if idx < 5:
                            logger.info(f"Найдено количество в элементе <Количество> для товара {product_id}: {quantity}")
                    except (ValueError, AttributeError) as e:
                        if idx < 5:
                            logger.warning(f"Не удалось распарсить остаток из <Количество> для товара {product_id}: {quantity_elem.text}, ошибка: {e}")
                
                # Вариант 2: Если не нашли в элементе, ищем в атрибуте <Склад КоличествоНаСкладе="..."/>
                if quantity is None:
                    warehouse_elem = None
                    if namespace:
                        warehouse_elem = offer_elem.find(f'.//{{{namespace}}}Склад')
                    if warehouse_elem is None:
                        warehouse_elem = offer_elem.find('.//Склад')
                    if warehouse_elem is None and 'catalog' in namespaces:
                        try:
                            warehouse_elem = offer_elem.find('.//catalog:Склад', namespaces)
                        except (KeyError, ValueError):
                            pass
                    
                    if warehouse_elem is not None:
                        # Ищем атрибут КоличествоНаСкладе
                        quantity_attr = warehouse_elem.get('КоличествоНаСкладе')
                        if not quantity_attr:
                            # Пробуем английское название атрибута
                            quantity_attr = warehouse_elem.get('QuantityInStock')
                        
                        if quantity_attr:
                            try:
                                quantity = int(float(str(quantity_attr).strip().replace(',', '.')))
                                if idx < 5:
                                    logger.info(f"Найдено количество в атрибуте Склад для товара {product_id}: {quantity}")
                            except (ValueError, AttributeError) as e:
                                if idx < 5:
                                    logger.warning(f"Не удалось распарсить остаток из атрибута Склад для товара {product_id}: {quantity_attr}, ошибка: {e}")
                
                # Обновляем количество и наличие
                # ВАЖНО: Определяем текущую цену ПОСЛЕ обновления цены выше
                # Для оптового каталога проверяем wholesale_price, для розничного - price
                if catalog_type == 'wholesale':
                    current_price = product.wholesale_price
                else:
                    current_price = product.price
                
                if quantity is not None:
                    product.quantity = quantity
                    # Определяем наличие и активность на основе остатка и цены
                    # ВАЖНО: В обоих каталогах товар активен, если есть остаток ИЛИ есть цена
                    if quantity > 0:
                        product.availability = 'in_stock'
                        product.is_active = True  # Товар с остатком - всегда активен
                    elif current_price and current_price > 0:
                        product.availability = 'order'  # Под заказ, если есть цена
                        product.is_active = True  # Товар с ценой - активен (под заказ) в обоих каталогах
                    else:
                        product.availability = 'out_of_stock'
                        product.is_active = False  # Товар без остатка и без цены - скрываем
                    if idx < 5:
                        logger.info(f"✓ Обновлен остаток для товара {product_id}: {quantity}, наличие: {product.availability}, активен: {product.is_active}, цена: {current_price}")
                else:
                    # Если количество не найдено, оставляем товар активным, если есть цена
                    # Товар может быть доступен под заказ
                    product.quantity = 0
                    # Проверяем цену ПОСЛЕ обновления
                    # Для оптового каталога проверяем wholesale_price, для розничного - price
                    if catalog_type == 'wholesale':
                        current_price = product.wholesale_price
                    else:
                        current_price = product.price
                    
                    # ВАЖНО: В обоих каталогах товар активен, если есть цена
                    if current_price and current_price > 0:
                        product.availability = 'order'  # Под заказ, если есть цена
                        product.is_active = True  # Товар с ценой - активен (под заказ) в обоих каталогах
                    else:
                        product.availability = 'out_of_stock'
                        product.is_active = False  # Товар без цены - скрываем
                    if idx < 10:
                        if product.is_active:
                            logger.info(f"⚠ Количество не найдено для товара {product_id}, но товар активен (есть цена: {current_price}).")
                        else:
                            logger.warning(f"⚠ Количество не найдено для товара {product_id} и нет цены. Товар скрыт.")
                        # Выводим структуру элемента для отладки
                        if idx < 3:
                            logger.debug(f"  Структура предложения: tag={offer_elem.tag}, children={[child.tag for child in offer_elem]}")
                            # Ищем все элементы с количеством
                            all_quantity_elems = offer_elem.findall('.//Количество')
                            if namespace:
                                all_quantity_elems.extend(offer_elem.findall(f'.//{{{namespace}}}Количество'))
                            logger.debug(f"  Найдено элементов <Количество>: {len(all_quantity_elems)}")
                            for q_elem in all_quantity_elems:
                                logger.debug(f"    <Количество>: {q_elem.text}")
                            # Ищем все элементы Склад
                            all_warehouse_elems = offer_elem.findall('.//Склад')
                            if namespace:
                                all_warehouse_elems.extend(offer_elem.findall(f'.//{{{namespace}}}Склад'))
                            logger.debug(f"  Найдено элементов <Склад>: {len(all_warehouse_elems)}")
                            for w_elem in all_warehouse_elems:
                                logger.debug(f"    <Склад> атрибуты: {w_elem.attrib}")
                
                product.save()
                processed_count += 1
                updated_count += 1
                
                # Логируем успешное обновление для первых товаров
                if idx < 10:
                    current_price = product.price if catalog_type == 'retail' else product.wholesale_price
                    logger.info(f"✓ Товар обновлен: Ид={product_id}, название={product.name[:50]}, цена={current_price}, остаток={product.quantity}, активен={product.is_active}, каталог={catalog_type}")
                
        except Exception as e:
            # Исключение при обработке предложения - транзакция автоматически откатывается
            error_msg = str(e)
            logger.error(f"✗ Исключение при обработке предложения #{idx+1}: {error_msg}", exc_info=True)
            errors.append({
                'offer_id': product_id if 'product_id' in locals() else f'offer_{idx}',
                'error': error_msg
            })
            # Транзакция автоматически откатывается при исключении
            # Продолжаем обработку следующего предложения
    
    processing_time = (timezone.now() - start_time).total_seconds()
    request_ip = get_client_ip(request) if request else None
    
    # ВАЖНО: Статус 'success' только если товары действительно обработаны
    if processed_count == 0:
        status = 'failure'
        message = f'Файл {filename} обработан, но товары не были обновлены для каталога {catalog_type}'
    elif errors:
        status = 'partial'
        message = f'Обработано предложений из файла {filename} для каталога {catalog_type} (с ошибками)'
    else:
        status = 'success'
        message = f'Обработано предложений из файла {filename} для каталога {catalog_type}'
    
    sync_log = SyncLog.objects.create(
        operation_type='file_upload',
        status=status,
        message=message,
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


def process_product_from_commerceml(product_data, catalog_type='retail'):
    """
    Обрабатывает товар из CommerceML формата.
    Использует логику из process_bulk_import для правильной обработки товаров.
    """
    from .services import parse_product_name, get_category_for_product
    from .models import Product, ProductCharacteristic
    import re
    
    try:
        # Получаем основные данные
        external_id = product_data.get('external_id') or product_data.get('sku', '')
        # Убираем пробелы и проверяем, что external_id не пустой
        if external_id:
            external_id = external_id.strip()
        if not external_id:
            external_id = None  # Используем None вместо пустой строки
        
        name = product_data.get('name', '').strip()
        article = product_data.get('article', '').strip()
        
        if not name:
            return None, "Отсутствует название товара", False
        
        if not external_id and not article:
            return None, "Отсутствует идентификатор товара (Ид или Артикул)", False
        
        # Логируем для диагностики (только первые 3 товара)
        if hasattr(process_product_from_commerceml, '_log_count'):
            process_product_from_commerceml._log_count += 1
        else:
            process_product_from_commerceml._log_count = 1
        
        if process_product_from_commerceml._log_count <= 3:
            logger.info(f"Обработка товара: external_id={external_id}, article={article}, name={name[:50]}")
        
        # Парсим название для извлечения бренда, артикула и т.д.
        parsed = parse_product_name(name)
        
        # Используем артикул из данных или из парсинга
        if not article and parsed.get('article'):
            article = parsed['article']
        if not article and external_id:
            article = external_id
        
        # Определяем бренд - всегда строка, не None
        # Сначала берем из XML, потом из парсинга названия, потом пытаемся определить из названия напрямую
        brand = (product_data.get('brand', '') or '').strip()
        if not brand:
            brand = (parsed.get('brand', '') or '').strip()
        if not brand:
            # Если бренд не найден, пытаемся определить из названия напрямую
            from .services import detect_brand
            detected_brand = detect_brand(name)
            if detected_brand:
                brand = detected_brand
        brand = brand or ''  # Всегда строка, не None
        
        # Формируем чистое название товара на основе парсинга
        # Сначала убираем лишние запятые, скобки и пробелы из исходного названия
        clean_name = name
        
        # Убираем множественные запятые и пробелы
        clean_name = re.sub(r',+', ',', clean_name)  # Множественные запятые -> одна
        clean_name = re.sub(r'\s+', ' ', clean_name)  # Множественные пробелы -> один
        clean_name = re.sub(r'\(\s*,', '(', clean_name)  # Пробелы и запятые после открывающей скобки
        clean_name = re.sub(r',\s*\)', ')', clean_name)  # Пробелы и запятые перед закрывающей скобкой
        clean_name = re.sub(r'\(\s*\)', '', clean_name)  # Пустые скобки
        clean_name = re.sub(r',\s*,', ',', clean_name)  # Запятые подряд
        clean_name = clean_name.strip(' ,()')  # Убираем запятые и скобки в начале/конце
        
        # Если название начинается с категории и содержит скобки, правильно обрабатываем скобки
        # Пример: "Датчик кислородный (TOYOTA,, 89467-71020,,,, 2UZFE/1GRFE,,,...)"
        # Должно стать: "Датчик кислородный (TOYOTA, 89467-71020, 2UZFE/1GRFE)"
        if '(' in clean_name:
            # Находим все открывающие и закрывающие скобки
            open_brackets = [i for i, char in enumerate(clean_name) if char == '(']
            close_brackets = [i for i, char in enumerate(clean_name) if char == ')']
            
            # Если есть незакрытые скобки, добавляем закрывающую скобку в конец
            if len(open_brackets) > len(close_brackets):
                clean_name = clean_name + ')'
            
            # Обрабатываем содержимое скобок
            bracket_matches = list(re.finditer(r'\(([^)]*)\)', clean_name))
            if bracket_matches:
                # Обрабатываем каждую пару скобок
                for match in reversed(bracket_matches):  # Обрабатываем с конца, чтобы индексы не сбились
                    content = match.group(1)
                    # Убираем лишние запятые и пробелы из содержимого
                    content = re.sub(r',+', ',', content)  # Множественные запятые -> одна
                    content = re.sub(r'\s+', ' ', content).strip()  # Множественные пробелы -> один
                    content = content.strip(',').strip()  # Убираем запятые в начале/конце
                    
                    # Заменяем содержимое скобок
                    start, end = match.span()
                    clean_name = clean_name[:start+1] + content + clean_name[end-1:]
            else:
                # Если есть открывающая скобка, но нет закрывающей, обрабатываем содержимое до конца
                last_open = clean_name.rfind('(')
                if last_open >= 0:
                    content = clean_name[last_open+1:]
                    # Убираем лишние запятые и пробелы
                    content = re.sub(r',+', ',', content)
                    content = re.sub(r'\s+', ' ', content).strip()
                    content = content.strip(',').strip()
                    clean_name = clean_name[:last_open+1] + content + ')'
        
        # Убираем оставшиеся лишние запятые и пробелы
        clean_name = re.sub(r',\s*,', ',', clean_name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Финальная очистка: убираем запятые в начале и конце, множественные запятые
        clean_name = re.sub(r'^,+|,+$', '', clean_name)  # Запятые в начале/конце
        clean_name = re.sub(r',\s*,', ',', clean_name)  # Множественные запятые
        clean_name = clean_name.strip()
        
        # Определяем категорию
        category_name = product_data.get('category_name', '').strip()
        if category_name:
            category = get_category_for_product(category_name)
        else:
            category = get_category_for_product(clean_name)
        
        # Обрабатываем цену (как в Excel импорте - убираем пробелы и невидимые символы)
        price = 0
        if 'price' in product_data:
            try:
                price_str = str(product_data['price']).strip().replace(',', '.').replace(' ', '').replace('\xa0', '')
                if price_str and price_str.lower() not in ['none', 'null', '']:
                    price = float(price_str)
                    if price < 0:
                        price = 0
            except (ValueError, TypeError):
                price = 0
        
        # Обрабатываем остаток
        quantity = 0
        if 'stock' in product_data:
            try:
                quantity = int(float(str(product_data['stock']).replace(',', '.')))
            except (ValueError, TypeError):
                quantity = 0
        
        # Определяем наличие и активность
        # ВАЖНО: В обоих каталогах (розничном и оптовом) товары должны быть активны, если есть остаток ИЛИ есть цена
        # Это обеспечивает идентичное количество активных товаров в обоих каталогах
        if catalog_type == 'wholesale':
            # В оптовом каталоге товар активен, если есть остаток ИЛИ есть оптовая цена
            # Используем price как оптовую цену (она будет установлена в wholesale_price)
            availability = 'in_stock' if quantity > 0 else ('order' if price > 0 else 'out_of_stock')
            is_active = quantity > 0 or price > 0
        else:
            # В розничном каталоге товар активен, если есть цена (может быть под заказ) или есть остаток
            # ВАЖНО: Товар должен быть активен, если есть остаток ИЛИ есть цена (даже если остаток 0)
            availability = 'in_stock' if quantity > 0 else ('order' if price > 0 else 'out_of_stock')
            is_active = quantity > 0 or price > 0
        
        # Ищем товар по external_id (приоритет) или по артикулу в нужном типе каталога
        product = None
        if external_id:
            product = Product.objects.filter(external_id=external_id, catalog_type=catalog_type).first()
        
        if not product and article:
            product = Product.objects.filter(article=article, catalog_type=catalog_type).first()
        
        was_created = product is None
        
        if was_created:
            # Создаем новый товар
            # external_id должен быть уникальным, поэтому используем его только если он есть
            # Если external_id пустой, используем None (не пустую строку), чтобы избежать конфликтов с unique=True
            product_external_id = external_id.strip() if external_id and external_id.strip() else None
            product = Product(
                external_id=product_external_id,
                article=article or '',
                name=clean_name or '',  # Используем чистое название
                brand=brand or '',  # Всегда строка, не None
                quantity=quantity or 0,
                availability=availability or 'out_of_stock',
                category=category,
                catalog_type=catalog_type,  # Используем переданный тип каталога
                is_active=is_active  # Активен только если есть остаток
            )
            # Для оптового каталога устанавливаем wholesale_price, для розничного - price
            if catalog_type == 'wholesale':
                product.wholesale_price = price
            else:
                product.price = price
        else:
            # Обновляем существующий товар
            # Всегда обновляем external_id, если он есть в данных (даже если уже был установлен)
            # Это важно для синхронизации с 1С
            if external_id and external_id.strip():
                product.external_id = external_id.strip()
            if article and not product.article:
                product.article = article
            product.name = clean_name  # Используем чистое название
            product.brand = brand or ''  # Всегда строка, не None
            # Обновляем цену только если она указана (не 0)
            # Это позволяет сохранить цену из offers.xml, если она уже была установлена
            # Для оптового каталога обновляем wholesale_price, для розничного - price
            if price > 0:
                if catalog_type == 'wholesale':
                    product.wholesale_price = price
                else:
                    product.price = price
            
            # ВАЖНО: Если товар создан из import.xml без цены, но потом придет цена из offers.xml,
            # нужно убедиться, что товар активируется после установки цены
            product.quantity = quantity
            product.availability = availability
            # ВАЖНО: Обновляем is_active в зависимости от остатка и цены
            # В оптовом каталоге товар активен только если есть остаток
            # ВАЖНО: В обоих каталогах товар активен, если есть остаток ИЛИ есть цена
            # Это обеспечивает идентичное количество активных товаров в обоих каталогах
            if catalog_type == 'wholesale':
                # В оптовом каталоге: активен если есть остаток ИЛИ есть оптовая цена
                current_price = product.wholesale_price
                product.is_active = quantity > 0 or (current_price and current_price > 0)
            else:
                # В розничном каталоге: активен если есть остаток ИЛИ есть цена
                current_price = product.price
                product.is_active = quantity > 0 or (current_price and current_price > 0)
            if category:
                product.category = category
        
        # Описание
        if product_data.get('description'):
            product.description = product_data.get('description')
        
        # Применимость - используем из парсинга или из данных
        # ВАЖНО: Артикулы НЕ должны попадать в применимость!
        applicability = None
        applicability_parts = []
        
        # Если applicability пришёл как список (из характеристик)
        if product_data.get('applicability'):
            if isinstance(product_data.get('applicability'), list):
                applicability_parts.extend(product_data.get('applicability'))
            else:
                applicability_parts.append(product_data.get('applicability'))
        
        # Добавляем из парсинга
        if parsed.get('applicability'):
            applicability_parts.append(parsed.get('applicability'))
        
        # ВАЖНО: TIS-166/GUIS-66 - это ПРИМЕНИМОСТЬ, не артикул!
        # Артикул = OEM номер (кросс-номер)
        # Применимость может содержать артикулы альтернативные (TIS-166, GUIS-66) - это нормально
        if applicability_parts:
            applicability = ', '.join([p for p in applicability_parts if p and str(p).strip()])
            if applicability:
                product.applicability = applicability
        
        # Кросс-номера - объединяем из разных источников
        cross_numbers_parts = []
        
        # Если cross_numbers пришёл как список (из характеристик)
        if product_data.get('cross_numbers'):
            if isinstance(product_data.get('cross_numbers'), list):
                cross_numbers_parts.extend(product_data.get('cross_numbers'))
            else:
                cross_numbers_parts.append(product_data.get('cross_numbers'))
        
        # Добавляем из парсинга
        if parsed.get('oem_number'):
            cross_numbers_parts.append(parsed.get('oem_number'))
        
        # Добавляем кросс-номера из парсинга (если они были извлечены из артикула со слешем)
        if parsed.get('cross_numbers'):
            if isinstance(parsed.get('cross_numbers'), list):
                cross_numbers_parts.extend(parsed.get('cross_numbers'))
            else:
                cross_numbers_parts.append(parsed.get('cross_numbers'))
        
        if cross_numbers_parts:
            cross_numbers = ', '.join([p for p in cross_numbers_parts if p and str(p).strip()])
            if cross_numbers:
                product.cross_numbers = cross_numbers
        
        # Характеристики - объединяем из парсинга названия и из XML
        characteristics_parts = []
        
        # Сначала добавляем характеристики из парсинга названия (это более надежно)
        import re
        excluded_materials = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
        
        if parsed.get('characteristics'):
            # parsed['characteristics'] - это строка с разделителями \n
            parsed_chars = parsed.get('characteristics').split('\n')
            for char_line in parsed_chars:
                char_line = char_line.strip()
                if char_line and ':' in char_line:
                    char_name, char_value = char_line.split(':', 1)
                    char_name_stripped = char_name.strip()
                    char_value_stripped = char_value.strip()
                    char_name_lower = char_name_stripped.lower()
                    char_value_upper = char_value_stripped.upper()
                    
                    # Пропускаем материалы
                    if any(material in char_name_lower for material in excluded_materials):
                        continue
                    
                    # Если это размер, проверяем, что это действительно размер
                    if 'размер' in char_name_lower or 'size' in char_name_lower:
                        # Размер должен содержать числа и * или x (например, 20*450)
                        if not re.search(r'\d+[*x]\d+', char_value_stripped):
                            # Это не размер, пропускаем
                            continue
                    
                    # Проверяем, что значение не является кодом модели/применимости
                    # Коды моделей обычно: 1-4 цифры + буквы (например, 1GEN, 1NZF, 2GR, 4AFE)
                    if re.match(r'^[A-Z0-9#\-/]{1,10}$', char_value_upper) and not re.search(r'[*x]', char_value_stripped):
                        # Это похоже на код модели, а не на характеристику - пропускаем
                        continue
                    
                    characteristics_parts.append(char_line)
        
        # Затем добавляем характеристики из XML (как список словарей)
        # ИСКЛЮЧАЕМ служебные характеристики: Артикул1, Артикул2, Марка, Двигатель
        excluded_chars = ['артикул1', 'артикул 1', 'article1', 'article 1',
                          'артикул2', 'артикул 2', 'article2', 'article 2', 'oem', 'oem номер',
                          'марка', 'brand', 'бренд',
                          'двигатель', 'engine', 'мотор']
        
        if product_data.get('characteristics'):
            char_list = product_data.get('characteristics', [])
            if isinstance(char_list, list):
                import re
                excluded_materials = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
                
                for char_data in char_list:
                    if isinstance(char_data, dict):
                        char_name = char_data.get('name', '').strip()
                        char_value = char_data.get('value', '').strip()
                        if char_name and char_value:
                            char_name_lower = char_name.lower()
                            char_value_upper = char_value.upper()
                            
                            # Пропускаем служебные характеристики
                            if char_name_lower in excluded_chars:
                                continue
                            
                            # Пропускаем материалы
                            if any(material in char_name_lower for material in excluded_materials):
                                continue
                            
                            # Если это размер, проверяем, что это действительно размер
                            if 'размер' in char_name_lower or 'size' in char_name_lower:
                                # Размер должен содержать числа и * или x (например, 20*450)
                                if not re.search(r'\d+[*x]\d+', char_value):
                                    # Это не размер, пропускаем
                                    continue
                            
                            # Проверяем, что значение не является кодом модели/применимости
                            # Коды моделей обычно: 1-4 цифры + буквы (например, 1GEN, 1NZF, 2GR, 4AFE)
                            # Или только буквы+цифры без * или x
                            if re.match(r'^[A-Z0-9#\-/]{1,10}$', char_value_upper) and not re.search(r'[*x]', char_value):
                                # Это похоже на код модели, а не на характеристику - пропускаем
                                continue
                            
                            char_str = f"{char_name}: {char_value}"
                            # Проверяем, нет ли уже такой характеристики
                            if not any(char_str in existing for existing in characteristics_parts):
                                characteristics_parts.append(char_str)
        
        # Объединяем все характеристики
        if characteristics_parts:
            product.characteristics = '\n'.join(characteristics_parts)
        
        # ВАЖНО: Сохраняем товар ПЕРЕД обработкой ProductCharacteristic
        # Это гарантирует, что товар будет создан даже если ProductCharacteristic не работает
        try:
            product.save()
            if was_created:
                logger.info(f"✓ Товар сохранен в БД: {product.external_id or product.article} (catalog_type={catalog_type})")
        except Exception as save_error:
            error_msg = f"Ошибка сохранения товара: {str(save_error)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg, False
        
        # Обрабатываем характеристики для ProductCharacteristic (если нужно)
        # Но основное поле characteristics уже заполнено выше
        # ВАЖНО: Проверяем существование таблицы ПЕРЕД использованием, чтобы не сломать транзакцию
        if product_data.get('characteristics') and isinstance(product_data.get('characteristics'), list):
            # Проверяем существование таблицы ProductCharacteristic
            from django.db import connection
            table_exists = False
            try:
                with connection.cursor() as cursor:
                    if 'sqlite' in connection.vendor:
                        cursor.execute("""
                            SELECT name FROM sqlite_master 
                            WHERE type='table' AND name='catalog_productcharacteristic'
                        """)
                    else:
                        cursor.execute("""
                            SELECT table_name FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = 'catalog_productcharacteristic'
                        """)
                    table_exists = cursor.fetchone() is not None
            except Exception:
                table_exists = False
            
            if table_exists:
                try:
                    # Пытаемся удалить старые ProductCharacteristic
                    ProductCharacteristic.objects.filter(product=product).delete()
                    
                    # Создаем новые ProductCharacteristic
                    for idx, char_data in enumerate(product_data.get('characteristics', [])):
                        if isinstance(char_data, dict):
                            char_name = char_data.get('name', '').strip()
                            char_value = char_data.get('value', '').strip()
                            if char_name and char_value:
                                ProductCharacteristic.objects.create(
                                    product=product,
                                    name=char_name,
                                    value=char_value,
                                    order=idx
                                )
                except Exception as char_error:
                    # Если произошла ошибка - просто пропускаем создание характеристик,
                    # но не ломаем обработку товара
                    error_msg = str(char_error)
                    # Логируем только если это не ошибка отсутствия таблицы (чтобы не засорять логи)
                    if 'no such table' not in error_msg.lower() and 'does not exist' not in error_msg.lower():
                        logger.warning(f"Не удалось обработать ProductCharacteristic для товара {product.external_id or product.article}: {error_msg}")
                    # Характеристики уже сохранены в поле product.characteristics, так что это не критично
            # Если таблица не существует, просто пропускаем - характеристики уже сохранены в product.characteristics
        
        return product, None, was_created
        
    except Exception as e:
        error_msg = f"Ошибка обработки товара: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg, False
