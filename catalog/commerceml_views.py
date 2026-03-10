"""
Views для обработки стандартного протокола CommerceML 2 обмена с 1С.
Протокол разработан компаниями «1С» и «1С-Битрикс».
"""
import os
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, OperationalError
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


def invalidate_category_cache(category, force=False):
    """
    Инвалидирует кеш подсчета товаров для категории и всех её родителей.
    
    Args:
        category: Категория для инвалидации кеша
        force: Если True, очищает кеш принудительно. 
               Если False, очищает только при создании/удалении товаров (не при обновлении)
    """
    if not category:
        return
    
    # ВАЖНО: Очищаем кеш только при создании/удалении товаров (force=True)
    # При обновлении товаров из offers.xml кеш НЕ очищаем для стабильности
    if not force:
        return
    
    from django.core.cache import cache
    # Инвалидируем кеш для текущей категории и всех родительских
    current = category
    while current:
        cache_key = f'category_product_count_{current.id}'
        cache.delete(cache_key)
        current = current.parent


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
            
            # ВАЖНО: Сохраняем processed_external_ids из offers.xml для использования в логике скрытия
            # Это нужно, чтобы товары из offers.xml не скрывались при обработке import.xml
            offers_processed_external_ids = set()
            if isinstance(result_retail.get('processed_external_ids'), set):
                offers_processed_external_ids.update(result_retail.get('processed_external_ids', set()))
            if isinstance(result_wholesale.get('processed_external_ids'), set):
                offers_processed_external_ids.update(result_wholesale.get('processed_external_ids', set()))
            
            # Сохраняем в request для использования в process_commerceml_file
            if request:
                if not hasattr(request, '_offers_processed_external_ids'):
                    request._offers_processed_external_ids = {}
                request._offers_processed_external_ids['retail'] = result_retail.get('processed_external_ids', set())
                request._offers_processed_external_ids['wholesale'] = result_wholesale.get('processed_external_ids', set())
                logger.info(f"Сохранено {len(offers_processed_external_ids)} external_id из offers.xml для использования в логике скрытия")
            
            # Объединяем результаты
            return {
                'status': 'success' if result_retail.get('status') == 'success' and result_wholesale.get('status') == 'success' else 'partial',
                'processed': result_retail.get('processed', 0) + result_wholesale.get('processed', 0),
                'updated': result_retail.get('updated', 0) + result_wholesale.get('updated', 0),
                'errors': result_retail.get('errors', []) + result_wholesale.get('errors', []),
                'processed_external_ids': offers_processed_external_ids  # Объединенные ID из обоих каталогов
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
        
        # Оптимизация: создаем кэш групп один раз перед обработкой товаров
        # Это значительно ускоряет обработку больших XML файлов
        groups_cache = {}
        logger.info("Создание кэша групп для оптимизации поиска категорий...")
        try:
            # Ищем Классификатор/Группы
            classifier = None
            if namespace:
                classifier = root.find(f'.//{{{namespace}}}Классификатор')
            if classifier is None:
                classifier = root.find('.//Классификатор')
            if classifier is None and 'catalog' in namespaces:
                try:
                    classifier = root.find('.//catalog:Классификатор', namespaces)
                except (KeyError, ValueError):
                    pass
            
            if classifier is not None:
                # Ищем все группы
                groups = []
                if namespace:
                    groups = classifier.findall(f'.//{{{namespace}}}Группа')
                if not groups:
                    groups = classifier.findall('.//Группа')
                if not groups and 'catalog' in namespaces:
                    try:
                        groups = classifier.findall('.//catalog:Группа', namespaces)
                    except (KeyError, ValueError):
                        pass
                
                # Кэшируем группы по Ид
                for group in groups:
                    group_id = None
                    group_name = None
                    
                    # Ищем Ид группы
                    id_elem = None
                    if namespace:
                        id_elem = group.find(f'{{{namespace}}}Ид')
                    if id_elem is None:
                        id_elem = group.find('Ид')
                    if id_elem is None and 'catalog' in namespaces:
                        try:
                            id_elem = group.find('catalog:Ид', namespaces)
                        except (KeyError, ValueError):
                            pass
                    if id_elem is not None and id_elem.text:
                        group_id = id_elem.text.strip()
                    
                    # Ищем Наименование группы
                    name_elem = None
                    if namespace:
                        name_elem = group.find(f'{{{namespace}}}Наименование')
                    if name_elem is None:
                        name_elem = group.find('Наименование')
                    if name_elem is None and 'catalog' in namespaces:
                        try:
                            name_elem = group.find('catalog:Наименование', namespaces)
                        except (KeyError, ValueError):
                            pass
                    if name_elem is not None and name_elem.text:
                        group_name = name_elem.text.strip()
                    
                    if group_id and group_name:
                        groups_cache[group_id] = group_name
                
                logger.info(f"Кэш групп создан: {len(groups_cache)} групп")
            else:
                logger.warning("Классификатор не найден, кэш групп не создан")
        except Exception as e:
            logger.warning(f"Ошибка при создании кэша групп: {e}, продолжаем без кэша")
        
        # ВАЖНО: Собираем все варианты товаров, но для товаров с одинаковым базовым Ид
        # используем данные из ПОСЛЕДНЕГО варианта (это измененные данные из 1С)
        # Все товары имеют Ид, поэтому группируем только по базовому Ид
        products_by_base_id = {}  # Словарь: базовый_Ид -> последние данные товара
        
        for idx, product_elem in enumerate(products_elements):
            product_data = parse_commerceml_product(product_elem, namespaces, root, groups_cache=groups_cache)
            if product_data:
                # Определяем базовый Ид товара (все товары имеют Ид)
                external_id = product_data.get('external_id') or product_data.get('sku', '')
                if external_id:
                    external_id = external_id.strip()
                    # Если Ид составной (содержит #), извлекаем базовый Ид
                    if '#' in external_id:
                        base_id = external_id.split('#')[0]
                    else:
                        base_id = external_id
                    
                    # ВАЖНО: Обновляем external_id в product_data на базовый Ид
                    # Это гарантирует, что при обработке будет использоваться базовый Ид
                    product_data['external_id'] = base_id
                    product_data['sku'] = base_id
                    
                    # ВАЖНО: Если товар с таким базовым Ид уже встречался,
                    # заменяем его данными на последний вариант (измененные данные из 1С)
                    if base_id in products_by_base_id:
                        # Логируем для диагностики
                        old_name = products_by_base_id[base_id].get('name', '')[:50]
                        new_name = product_data.get('name', '')[:50]
                        logger.info(f"Товар #{idx+1}: найден дубликат базового Ид {base_id}")
                        logger.info(f"  Старое название: {old_name}")
                        logger.info(f"  Новое название: {new_name}")
                        logger.info(f"  → Используем данные из последнего варианта (измененные из 1С)")
                        products_by_base_id[base_id] = product_data
                    else:
                        products_by_base_id[base_id] = product_data
                else:
                    # Если по какой-то причине Ид отсутствует, добавляем товар как есть
                    # (но по словам пользователя таких товаров нет)
                    products_data.append(product_data)
                    logger.warning(f"Товар #{idx+1}: отсутствует Ид, добавлен как есть")
                
                if idx < 3:  # Логируем первые 3 товара для отладки
                    logger.info(f"Товар #{idx+1}: sku={product_data.get('sku')}, name={product_data.get('name')[:50] if product_data.get('name') else 'N/A'}")
            else:
                logger.warning(f"Товар #{idx+1}: не удалось распарсить (нет обязательных полей)")
                # Выводим структуру элемента для отладки
                if idx < 3:
                    logger.warning(f"  Структура элемента: tag={product_elem.tag}, атрибуты={product_elem.attrib}")
                    for child in product_elem:
                        logger.warning(f"    Дочерний: {child.tag} = {child.text[:50] if child.text else 'None'}")
        
        # Добавляем все уникальные товары (последние варианты для каждого базового Ид)
        products_data.extend(products_by_base_id.values())
        
        logger.info(f"Всего распарсено товаров: {len(products_data)} (уникальных по базовому Ид: {len(products_by_base_id)})")
        
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
            
            # ВАЖНО: Сбрасываем счетчики для каждого каталога
            # Иначе данные из retail будут смешиваться с данными из wholesale
            processed_count = 0
            created_count = 0
            updated_count = 0
            errors = []
            # ВАЖНО: Собираем external_id только из успешно обработанных товаров для текущего типа каталога
            processed_external_ids = set()
            
            logger.info(f"Начало обработки {len(products_data)} товаров для каталога {current_catalog_type} (оптимизированная обработка)")
        
        # ВАЖНО: Обрабатываем товары батчами для производительности
        # Но все равно в отдельных транзакциях для надежности
        batch_size = 100  # Обрабатываем по 100 товаров за раз
        for batch_start in range(0, len(products_data), batch_size):
            batch_end = min(batch_start + batch_size, len(products_data))
            batch = products_data[batch_start:batch_end]
            logger.info(f"Обработка батча {batch_start+1}-{batch_end} из {len(products_data)} товаров для {current_catalog_type}")
            
            for idx, product_data in enumerate(batch):
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
                            # ВАЖНО: Добавляем external_id только если товар успешно обработан для текущего типа каталога
                            external_id = product.external_id or product_data.get('external_id') or product_data.get('sku')
                            if external_id:
                                processed_external_ids.add(str(external_id).strip())
                                
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
            logger.info(f"Обработано товаров в обмене: {len(processed_external_ids)} с external_id для каталога {current_catalog_type}")
            
            # Сохраняем результаты для текущего каталога
            results[current_catalog_type] = {
                'processed': processed_count,
                'created': created_count,
                'updated': updated_count,
                'deleted': 0,  # Будет обновлено после скрытия товаров
                'errors': errors.copy(),  # Копируем список ошибок
                'processed_external_ids': processed_external_ids.copy()  # Сохраняем для скрытия товаров
            }
            
            # Суммируем общие результаты
            total_processed += processed_count
            total_created += created_count
            total_updated += updated_count
            all_errors.extend(errors)
        
        # ВАЖНО: Скрываем товары ТОЛЬКО ПОСЛЕ обработки всех каталогов
        # Это предотвращает ситуацию, когда товары скрываются/показываются во время обработки
        # ВАЖНО: Скрываем товары ТОЛЬКО при обработке через веб-интерфейс (когда 1С загружает файлы напрямую)
        # При обработке через скрипт (request=None) НЕ скрываем товары - это может быть повторная обработка
        should_hide_products = False
        
        # Если обработка через скрипт (request=None), НЕ скрываем товары вообще
        if request is None:
            logger.info(f"Обработка через скрипт (request=None) - НЕ скрываем товары для безопасности (предотвращает случайное скрытие при повторной обработке)")
            should_hide_products = False
        else:
            # Обработка через веб-интерфейс - проверяем, нужно ли скрывать товары
            # Проверяем тип файла - скрываем товары только для import.xml
            filename_lower = filename.lower() if filename else ''
            is_import_file = 'import' in filename_lower and 'offers' not in filename_lower
            
            if is_import_file and file_path and os.path.exists(file_path):
                processed_marker = f"{file_path}.processed"
                if os.path.exists(processed_marker):
                    # Файл уже обрабатывался - проверяем, изменился ли он
                    # ВАЖНО: Используем file_mtime из маркера, а не время создания маркера
                    try:
                        # Получаем текущее время файла
                        file_mtime = os.path.getmtime(file_path)
                        file_mtime_dt = datetime.fromtimestamp(file_mtime)
                        
                        # Пытаемся прочитать время файла из маркера (если оно там сохранено)
                        file_mtime_from_marker = None
                        try:
                            with open(processed_marker, 'r') as f:
                                for line in f:
                                    if line.startswith('file_mtime:'):
                                        file_mtime_from_marker = datetime.fromisoformat(line.split(':', 1)[1].strip())
                                        break
                        except Exception:
                            pass
                        
                        # Если время файла сохранено в маркере, используем его
                        # Иначе используем время маркера (старая логика для обратной совместимости)
                        if file_mtime_from_marker:
                            # Сравниваем текущее время файла с временем из маркера
                            if file_mtime_dt > file_mtime_from_marker:
                                should_hide_products = True
                                logger.info(f"Файл import.xml изменен после последней обработки (файл: {file_mtime_dt}, маркер: {file_mtime_from_marker}) - скрываем товары, не пришедшие в обмене")
                            else:
                                should_hide_products = False
                                logger.info(f"Файл import.xml НЕ изменился с последней обработки (файл: {file_mtime_dt}, маркер: {file_mtime_from_marker}) - НЕ скрываем товары")
                        else:
                            # Старая логика - сравниваем с временем маркера (для обратной совместимости)
                            marker_mtime = os.path.getmtime(processed_marker)
                            marker_mtime_dt = datetime.fromtimestamp(marker_mtime)
                            if file_mtime_dt > marker_mtime_dt:
                                should_hide_products = True
                                logger.info(f"Файл import.xml изменен после последней обработки (файл: {file_mtime_dt}, маркер: {marker_mtime_dt}) - скрываем товары, не пришедшие в обмене")
                            else:
                                should_hide_products = False
                                logger.info(f"Файл import.xml НЕ изменился с последней обработки (файл: {file_mtime_dt}, маркер: {marker_mtime_dt}) - НЕ скрываем товары")
                    except Exception as e:
                        # Если не удалось проверить - НЕ скрываем товары (безопаснее)
                        should_hide_products = False
                        logger.warning(f"Не удалось проверить время изменения файла: {e}, НЕ скрываем товары для безопасности")
                else:
                    # Файл новый (нет маркера) - скрываем товары (это новая загрузка из 1С через веб-интерфейс)
                    should_hide_products = True
                    logger.info(f"Файл import.xml новый (нет маркера) - скрываем товары, не пришедшие в обмене")
            else:
                # Для offers.xml или если не можем определить файл - НЕ скрываем товары
                should_hide_products = False
                if not is_import_file:
                    logger.info(f"Файл {filename} - это offers.xml, НЕ скрываем товары (только обновляем цены и остатки)")
                else:
                    logger.warning(f"⚠ Не удалось определить путь к файлу или файл не существует - НЕ скрываем товары")
        
        # Находим товары, которые были импортированы из 1С (имеют external_id),
        # но не пришли в текущем обмене
        # ВАЖНО: Скрываем только товары из того же типа каталога (retail или wholesale)
        # И ТОЛЬКО ЕСЛИ ФАЙЛ НОВЫЙ/ИЗМЕНЕННЫЙ
        # ВАЖНО: Скрываем товары ТОЛЬКО после обработки всех каталогов
        total_deleted = 0
        if should_hide_products:
            for current_catalog_type in ['retail', 'wholesale']:
                catalog_results = results.get(current_catalog_type, {})
                processed_external_ids = catalog_results.get('processed_external_ids', set())
                processed_count = catalog_results.get('processed', 0)
                errors_count = len(catalog_results.get('errors', []))
                
                # ВАЖНО: Объединяем processed_external_ids из import.xml и offers.xml
                # Товары из offers.xml тоже должны учитываться при логике скрытия
                # Это критично, потому что:
                # - import.xml содержит информацию о товарах (названия, характеристики)
                # - offers.xml содержит цены и количества
                # - Оба файла обрабатываются параллельно, и товары должны быть видны, если они есть хотя бы в одном из них
                import_ids_count = len(processed_external_ids)
                if request and hasattr(request, '_offers_processed_external_ids'):
                    offers_ids = request._offers_processed_external_ids.get(current_catalog_type, set())
                    if offers_ids:
                        processed_external_ids = processed_external_ids.union(offers_ids)
                        logger.info(f"✓ Объединено {len(offers_ids)} external_id из offers.xml с {import_ids_count} из import.xml для каталога {current_catalog_type} (всего: {len(processed_external_ids)})")
                    else:
                        logger.info(f"⚠ Нет external_id из offers.xml для каталога {current_catalog_type} (возможно, offers.xml еще не обработан)")
                else:
                    logger.info(f"⚠ Нет сохраненных external_id из offers.xml (request=None или offers.xml не обработан)")
                
                # ВАЖНО: Скрываем товары ТОЛЬКО если были обработаны товары для этого типа каталога (processed_count > 0)
                # И если количество ошибок не слишком большое (более 50% ошибок - не скрываем товары для безопасности)
                # Это предотвращает скрытие всех товаров, если в обмене не было товаров для этого типа каталога
                # или если было много ошибок обработки (например, "database is locked")
                total_attempts = processed_count + errors_count
                error_rate = errors_count / total_attempts if total_attempts > 0 else 0
                
                if processed_external_ids and processed_count > 0 and error_rate < 0.5:
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
                        
                        # ВАЖНО: НЕ обнуляем quantity при скрытии товаров!
                        # Количество должно сохраняться, чтобы при следующем обмене товары могли восстановиться
                        # Скрываем товары (не удаляем физически, чтобы сохранить историю)
                        products_to_hide.update(is_active=False, availability='out_of_stock')
                        # НЕ обнуляем quantity - оставляем существующее значение
                        logger.info(f"✓ Скрыто товаров в каталоге {current_catalog_type}: {deleted_count} (количество сохранено)")
                        total_deleted += deleted_count
                        # Обновляем результаты для текущего каталога
                        results[current_catalog_type]['deleted'] = deleted_count
                    else:
                        logger.info(f"Все товары из 1С присутствуют в обмене для каталога {current_catalog_type}, скрывать нечего")
                elif processed_count == 0:
                    logger.warning(f"⚠ В обмене нет товаров для каталога {current_catalog_type} (processed_count=0) - НЕ скрываем товары (предотвращает случайное скрытие всех товаров)")
                elif error_rate >= 0.5:
                    logger.warning(f"⚠ Слишком много ошибок обработки для каталога {current_catalog_type} (ошибок: {errors_count}, обработано: {processed_count}, процент ошибок: {error_rate*100:.1f}%) - НЕ скрываем товары для безопасности (могут быть пропущены из-за ошибок)")
                else:
                    logger.warning(f"⚠ В обмене нет товаров с external_id для каталога {current_catalog_type} - невозможно определить удаленные товары")
        elif not should_hide_products:
            logger.info(f"Файл не изменился или обработка через скрипт - НЕ скрываем товары")
        
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
        
        # ВАЖНО: Создаем маркер обработанного файла, чтобы скрипт не обрабатывал его повторно
        # Это нужно как для прямого обмена, так и для обработки через скрипт
        # Создаем маркер только если товары действительно обработаны
        # ВАЖНО: Создаем маркер для оригинального файла (file_path), а не для распакованного (xml_file_path)
        if total_processed > 0:
            # Определяем, для какого файла создавать маркер
            # Если это ZIP, создаем маркер для ZIP файла
            # Если это XML, создаем маркер для XML файла
            marker_file_path = file_path  # По умолчанию для оригинального файла
            
            if file_path and os.path.exists(file_path):
                processed_marker = f"{marker_file_path}.processed"
                try:
                    file_mtime = os.path.getmtime(marker_file_path)
                    file_mtime_iso = datetime.fromtimestamp(file_mtime).isoformat()
                    with open(processed_marker, 'w') as f:
                        f.write(f'processed\n')
                        f.write(f'file_mtime: {file_mtime_iso}\n')  # Время изменения файла
                        f.write(f'marker_time: {timezone.now().isoformat()}\n')  # Время создания маркера
                        f.write(f'processed_count: {total_processed}\n')
                        f.write(f'created: {total_created}\n')
                        f.write(f'updated: {total_updated}\n')
                        f.write(f'processed_by: {"web_interface" if request else "script"}\n')  # Кто обработал
                    logger.info(f"✓ Создан маркер обработанного файла: {processed_marker}")
                    logger.info(f"  Файл: {marker_file_path}, размер маркера: {os.path.getsize(processed_marker)} байт")
                except Exception as marker_error:
                    logger.error(f"✗ Не удалось создать маркер обработанного файла: {marker_error}", exc_info=True)
            else:
                logger.warning(f"⚠ Не могу создать маркер: file_path={file_path}, существует={os.path.exists(file_path) if file_path else False}")
        else:
            logger.warning(f"⚠ Маркер не создан: total_processed={total_processed} (товары не обработаны)")
        
            # ВАЖНО: Проверяем существование таблицы SyncLog перед использованием
            from django.db import connection
            table_exists = False
            try:
                with connection.cursor() as cursor:
                    if 'sqlite' in connection.vendor:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_synclog'")
                    else:
                        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name='catalog_synclog'")
                    table_exists = cursor.fetchone() is not None
            except Exception:
                pass
            
            if table_exists:
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
        # ВАЖНО: results может не содержать ключи 'retail'/'wholesale' при частичных сценариях — не падаем на логировании
        retail_stats = results.get('retail') if isinstance(results, dict) else None
        wholesale_stats = results.get('wholesale') if isinstance(results, dict) else None
        if isinstance(retail_stats, dict):
            logger.info(
                f"  Розничный каталог: обработано={retail_stats.get('processed', 0)}, "
                f"создано={retail_stats.get('created', 0)}, обновлено={retail_stats.get('updated', 0)}"
            )
        else:
            logger.info("  Розничный каталог: нет данных статистики")
        if isinstance(wholesale_stats, dict):
            logger.info(
                f"  Оптовый каталог: обработано={wholesale_stats.get('processed', 0)}, "
                f"создано={wholesale_stats.get('created', 0)}, обновлено={wholesale_stats.get('updated', 0)}"
            )
        else:
            logger.info("  Оптовый каталог: нет данных статистики")
        
        # ВАЖНО: Логируем информацию о создании маркера для отладки
        logger.info(f"Проверка создания маркера: total_processed={total_processed}, file_path={file_path}, exists={os.path.exists(file_path) if file_path else False}")
        
        return {
            'status': 'success',
            'processed': total_processed,
            'created': total_created,
            'updated': total_updated,
            'deleted': total_deleted,
            'errors': len(all_errors),
            # Безопасно возвращаем статистику по каталогам (может отсутствовать в редких сценариях)
            'retail': results.get('retail', {}) if isinstance(results, dict) else {},
            'wholesale': results.get('wholesale', {}) if isinstance(results, dict) else {},
        }
        
    except ET.ParseError as e:
        return {'status': 'failure', 'error': f'Ошибка парсинга XML: {str(e)}'}
    except Exception as e:
        logger.error(f"Ошибка обработки файла CommerceML: {e}", exc_info=True)
        return {'status': 'failure', 'error': str(e)}


def parse_commerceml_product(product_elem, namespaces, root_elem=None, groups_cache=None):
    """
    Парсит элемент товара из CommerceML 2 XML.
    
    Возвращает словарь с данными товара в формате, совместимом с validate_product.
    
    Args:
        product_elem: Элемент товара из XML
        namespaces: Словарь с namespace
        root_elem: Корневой элемент XML (опционально, для поиска групп)
        groups_cache: Кэш групп {group_id: group_name} для оптимизации поиска
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
        full_id = id_elem.text.strip()
        # ВАЖНО: В CommerceML 2.0 товар с вариантами характеристик имеет составной Ид вида "uuid#characteristic_id"
        # Например: "13a33496-235b-4440-ab12-15b1eb281f06#4f02ca3d-c696-11f0-811a-00155d01d802"
        # Нужно извлечь основной Ид товара (до символа #)
        # Это позволяет обновлять один товар при наличии нескольких вариантов характеристик
        if '#' in full_id:
            base_id = full_id.split('#')[0]
            product_data['sku'] = base_id
            product_data['external_id'] = base_id
            product_data['full_external_id'] = full_id  # Сохраняем полный Ид для справки
            # Логируем для диагностики (только первые 3 товара)
            if not hasattr(parse_commerceml_product, '_log_count'):
                parse_commerceml_product._log_count = 0
            parse_commerceml_product._log_count += 1
            if parse_commerceml_product._log_count <= 3:
                logger.info(f"Найден составной Ид товара в XML: {full_id} -> базовый Ид: {base_id}")
        else:
            product_data['sku'] = full_id
            product_data['external_id'] = full_id
            # Логируем для диагностики (только первые 3 товара)
            if not hasattr(parse_commerceml_product, '_log_count'):
                parse_commerceml_product._log_count = 0
            parse_commerceml_product._log_count += 1
            if parse_commerceml_product._log_count <= 3:
                logger.info(f"Найден Ид товара в XML: {product_data['external_id']}")
    else:
        # Пробуем найти Ид в атрибутах
        if 'Ид' in product_elem.attrib:
            full_id = product_elem.attrib['Ид'].strip()
            # ВАЖНО: В CommerceML 2.0 товар с вариантами характеристик имеет составной Ид вида "uuid#characteristic_id"
            # Извлекаем основной Ид товара (до символа #)
            if '#' in full_id:
                base_id = full_id.split('#')[0]
                product_data['sku'] = base_id
                product_data['external_id'] = base_id
                product_data['full_external_id'] = full_id  # Сохраняем полный Ид для справки
                # Логируем для диагностики
                if not hasattr(parse_commerceml_product, '_log_count'):
                    parse_commerceml_product._log_count = 0
                parse_commerceml_product._log_count += 1
                if parse_commerceml_product._log_count <= 3:
                    logger.info(f"Найден составной Ид товара в атрибутах XML: {full_id} -> базовый Ид: {base_id}")
            else:
                product_data['sku'] = full_id
                product_data['external_id'] = full_id
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
        
        # Используем кэш групп для быстрого поиска (оптимизация производительности)
        if groups_cache and product_data['category_id'] in groups_cache:
            product_data['category_name'] = groups_cache[product_data['category_id']]
        elif root is not None:
            # Fallback: поиск в XML (медленнее, но работает если кэш не создан)
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
                # Извлекаем полное имя характеристики
                char_name = char_name_elem.text.strip() if char_name_elem.text else ''
                # Извлекаем полное значение характеристики, включая весь текст из элемента и дочерних элементов
                # Это важно для "Размера", который может содержать сложные значения типа "12V/140А/ПЛ.РЕМ.6Д/ОВ.Ф/ЗКОНТ"
                # Используем itertext() для сбора всего текста, включая дочерние элементы
                # ВАЖНО: Не используем strip() для каждой части, чтобы сохранить пробелы внутри значения
                char_value_parts = []
                for text in char_value_elem.itertext():
                    if text:
                        # Сохраняем текст как есть, только убираем лишние пробелы в начале/конце строк
                        char_value_parts.append(text)
                # Объединяем все части без добавления пробелов (они уже есть в тексте)
                char_value = ''.join(char_value_parts).strip() if char_value_parts else ''
                
                # Логируем извлечение "Размера" для отладки (только первые 3)
                if char_name and ('размер' in char_name.lower() or 'size' in char_name.lower()):
                    if not hasattr(parse_commerceml_product, '_log_size_extract_count'):
                        parse_commerceml_product._log_size_extract_count = 0
                    parse_commerceml_product._log_size_extract_count += 1
                    if parse_commerceml_product._log_size_extract_count <= 3:
                        logger.info(f"[XML] Извлечение 'Размер': name='{char_name}', value='{char_value}' (длина={len(char_value)})")
                
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
                    
                    # Двигатель → engine (для раздела "Применимость")
                    # ВАЖНО: Не добавляем в applicability здесь, чтобы избежать дублирования
                    # applicability будет заполнено из engine при сохранении товара
                    elif char_name_lower in ['двигатель', 'engine', 'мотор']:
                        if 'engine' not in product_data:
                            product_data['engine'] = []
                        if char_value not in product_data['engine']:
                            product_data['engine'].append(char_value)
                    
                    # Кузов → body (для раздела "Применимость"/описание)
                    # ВАЖНО: Не добавляем в applicability здесь, чтобы избежать дублирования
                    # applicability будет заполнено из body при сохранении товара
                    elif char_name_lower in ['кузов', 'body', 'тип кузова']:
                        if 'body' not in product_data:
                            product_data['body'] = []
                        if char_value not in product_data['body']:
                            product_data['body'].append(char_value)
                    
                    # Размер → всегда в характеристики (без фильтрации)
                    elif 'размер' in char_name_lower or 'size' in char_name_lower:
                        characteristics.append({
                            'name': char_name,
                            'value': char_value
                        })
                    
                    # Проверяем, является ли значение размером (например, 128*410 мм, 20*450, 260*170*10*29)
                    # ВАЖНО: Размеры могут быть в любых характеристиках, не только в поле "Размер"
                    elif re.search(r'\d+(?:\*|x)\d+(?:(?:\*|x)\d+)*(?:\s*(?:мм|см|м|mm|cm|m))?', char_value, re.IGNORECASE):
                        # Это размер - добавляем в характеристики как "Размер"
                        # Ищем существующий Размер в characteristics и заменяем его
                        size_found = False
                        for i, char in enumerate(characteristics):
                            if isinstance(char, dict) and ('размер' in char.get('name', '').lower() or 'size' in char.get('name', '').lower()):
                                # Объединяем значения, если размер уже есть
                                existing_value = char.get('value', '')
                                if char_value not in existing_value:
                                    characteristics[i] = {
                                        'name': 'Размер',
                                        'value': f"{existing_value}, {char_value}" if existing_value else char_value
                                    }
                                size_found = True
                                break
                        # Если не нашли, добавляем новый
                        if not size_found:
                            characteristics.append({
                                'name': 'Размер',
                            'value': char_value
                        })
                    
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
    # ВАЖНО: Обрабатываем ЗначенияСвойств всегда, даже если есть ХарактеристикиТовара,
    # так как в XML могут быть оба варианта одновременно
    props_elem = None
    prop_items = []  # ВАЖНО: всегда инициализируем, чтобы не было UnboundLocalError
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
        
    if prop_items:
            # ВАЖНО: Обрабатываем ЗначенияСвойств всегда для специальных полей (Артикул1, Артикул2, Двигатель, Кузов, Размер)
            # Эти поля должны браться из ЗначенияСвойств, а не из ХарактеристикиТовара
            # Для остальных характеристик добавляем только если characteristics пуст, чтобы избежать дублирования
            for prop_elem in prop_items:
                # Ищем Наименование свойства (приоритет)
                prop_name_elem = None
                if namespace:
                    prop_name_elem = prop_elem.find(f'{{{namespace}}}Наименование')
                if prop_name_elem is None:
                    prop_name_elem = prop_elem.find('Наименование')
                # Пробуем с префиксом catalog: только если он определен
                if prop_name_elem is None and 'catalog' in namespaces:
                    try:
                        prop_name_elem = prop_elem.find('catalog:Наименование', namespaces)
                    except (KeyError, ValueError):
                        pass
                
                # Если Наименование не найдено, используем Ид как fallback (для совместимости)
                if prop_name_elem is None:
                    prop_id_elem = None
                    if namespace:
                        prop_id_elem = prop_elem.find(f'{{{namespace}}}Ид')
                    if prop_id_elem is None:
                        prop_id_elem = prop_elem.find('Ид')
                    if prop_id_elem is None and 'catalog' in namespaces:
                        try:
                            prop_id_elem = prop_elem.find('catalog:Ид', namespaces)
                        except (KeyError, ValueError):
                            pass
                    if prop_id_elem is not None:
                        prop_name_elem = prop_id_elem  # Используем Ид как fallback
                
                # Ищем Значение свойства
                prop_value_elem = None
                if namespace:
                    prop_value_elem = prop_elem.find(f'{{{namespace}}}Значение')
                if prop_value_elem is None:
                    prop_value_elem = prop_elem.find('Значение')
                # Пробуем с префиксом catalog: только если он определен
                if prop_value_elem is None and 'catalog' in namespaces:
                    try:
                        prop_value_elem = prop_elem.find('catalog:Значение', namespaces)
                    except (KeyError, ValueError):
                        pass
                
                if prop_name_elem is not None and prop_value_elem is not None:
                    # Извлекаем полное имя свойства
                    prop_name = prop_name_elem.text.strip() if prop_name_elem.text else ''
                    # Извлекаем полное значение свойства, включая весь текст из элемента и дочерних элементов
                    prop_value_parts = []
                    for text in prop_value_elem.itertext():
                        if text:
                            prop_value_parts.append(text)
                    prop_val = ''.join(prop_value_parts).strip() if prop_value_parts else ''
                    
                    if prop_name:
                        prop_name_lower = prop_name.lower()
                        
                        # ВАЖНО: "Размер" обрабатываем ПЕРВЫМ и ВСЕГДА, даже если значение пустое!
                        # Это гарантирует, что значение "Размер" всегда попадет в характеристики
                        if 'размер' in prop_name_lower or 'size' in prop_name_lower:
                            # Ищем существующий Размер в characteristics и заменяем его
                            size_found = False
                            for i, char in enumerate(characteristics):
                                if isinstance(char, dict) and ('размер' in char.get('name', '').lower() or 'size' in char.get('name', '').lower()):
                                    characteristics[i] = {
                                        'name': prop_name,
                                        'value': prop_val  # Добавляем значение, даже если оно пустое
                                    }
                                    size_found = True
                                    break
                            # Если не нашли, добавляем новый
                            if not size_found:
                                characteristics.append({
                                    'name': prop_name,
                                    'value': prop_val  # Добавляем значение, даже если оно пустое
                                })
                            # Продолжаем обработку только если значение не пустое (для остальных полей)
                            if not prop_val:
                                continue
                        
                        # Обрабатываем служебные свойства - они не должны попадать в characteristics
                        # Артикул1 → article (кросс-номер)
                        if prop_name_lower in ['артикул1', 'артикул 1', 'article1', 'article 1']:
                            if not product_data.get('article'):
                                product_data['article'] = prop_val
                            # Добавляем в кросс-номера, если article уже был заполнен
                            elif product_data.get('article') != prop_val:
                                if 'cross_numbers' not in product_data:
                                    product_data['cross_numbers'] = []
                                if prop_val not in product_data['cross_numbers']:
                                    product_data['cross_numbers'].append(prop_val)
                        
                        # Артикул2 → cross_numbers (OEM номер)
                        elif prop_name_lower in ['артикул2', 'артикул 2', 'article2', 'article 2', 'oem', 'oem номер']:
                            if 'cross_numbers' not in product_data:
                                product_data['cross_numbers'] = []
                            if prop_val not in product_data['cross_numbers']:
                                product_data['cross_numbers'].append(prop_val)
                        
                        # Марка → brand (бренд)
                        elif prop_name_lower in ['марка', 'brand', 'бренд']:
                            product_data['brand'] = prop_val
                        
                        # Двигатель → engine (для раздела "Применимость")
                        # ВАЖНО: Не добавляем в applicability здесь, чтобы избежать дублирования
                        # applicability будет заполнено из engine при сохранении товара
                        elif prop_name_lower in ['двигатель', 'engine', 'мотор']:
                            if 'engine' not in product_data:
                                product_data['engine'] = []
                            if prop_val not in product_data['engine']:
                                product_data['engine'].append(prop_val)
                        
                        # Кузов → body (для раздела "Применимость"/описание)
                        # ВАЖНО: Не добавляем в applicability здесь, чтобы избежать дублирования
                        # applicability будет заполнено из body при сохранении товара
                        elif prop_name_lower in ['кузов', 'body', 'тип кузова']:
                            if 'body' not in product_data:
                                product_data['body'] = []
                            if prop_val not in product_data['body']:
                                product_data['body'].append(prop_val)
                        
                        # Проверяем, является ли значение размером (например, 128*410 мм, 20*450, 260*170*10*29)
                        # ВАЖНО: Размеры могут быть в любых характеристиках, не только в поле "Размер"
                        # Но только если поле НЕ называется "Размер" (так как "Размер" уже обработан выше)
                        elif prop_val and 'размер' not in prop_name_lower and 'size' not in prop_name_lower and re.search(r'\d+(?:\*|x)\d+(?:(?:\*|x)\d+)*(?:\s*(?:мм|см|м|mm|cm|m))?', prop_val, re.IGNORECASE):
                            # Это размер - добавляем в характеристики как "Размер"
                            # Ищем существующий Размер в characteristics и заменяем его
                            size_found = False
                            for i, char in enumerate(characteristics):
                                if isinstance(char, dict) and ('размер' in char.get('name', '').lower() or 'size' in char.get('name', '').lower()):
                                    # Объединяем значения, если размер уже есть
                                    existing_value = char.get('value', '')
                                    if prop_val not in existing_value:
                                        characteristics[i] = {
                                            'name': 'Размер',
                                            'value': f"{existing_value}, {prop_val}" if existing_value else prop_val
                                        }
                                    size_found = True
                                    break
                            # Если не нашли, добавляем новый
                            if not size_found:
                                characteristics.append({
                                    'name': 'Размер',
                                    'value': prop_val
                                })
                        
                        # Все остальные свойства добавляем в список
                        # ВАЖНО: Фильтруем неправильные значения (коды моделей, материалы и т.д.)
                        # ВАЖНО: Добавляем обычные характеристики только если characteristics пуст,
                        # чтобы избежать дублирования с ХарактеристикиТовара
                        else:
                            # Добавляем только если characteristics пуст (нет ХарактеристикиТовара)
                            if not characteristics:
                                # Исключаем материалы
                                excluded_materials = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
                                
                                # Пропускаем материалы
                                if any(material in prop_name_lower for material in excluded_materials):
                                    continue
                                
                                # Проверяем, что значение не является кодом модели/применимости
                                # Коды моделей обычно: 1-4 цифры + буквы (например, 1GEN, 1NZF, 2GR, 4AFE)
                                # Или только буквы+цифры без * или x
                                prop_val_upper = prop_val.upper()
                                if re.match(r'^[A-Z0-9#\-/]{1,10}$', prop_val_upper) and not re.search(r'[*x]', prop_val):
                                    # Это похоже на код модели, а не на характеристику - пропускаем
                                    continue
                                
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
    # ВАЖНО: Собираем external_id обработанных товаров для логики скрытия
    # Это нужно, чтобы товары из offers.xml не скрывались при обработке import.xml
    processed_external_ids = set()
    
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
    # ВАЖНО: Добавляем retry логику для обработки ошибок "database is locked" в SQLite
    logger.info(f"Начало обработки {len(offers)} предложений (каждое в отдельной транзакции с retry)")
    
    def process_offer_with_retry(offer_elem, idx, max_retries=3):
        """Обрабатывает предложение с повторными попытками при ошибке 'database is locked'"""
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    return process_single_offer(offer_elem, idx)
            except OperationalError as e:
                error_str = str(e).lower()
                if 'database is locked' in error_str or 'locked' in error_str:
                    if attempt < max_retries - 1:
                        # Экспоненциальная задержка: 0.1, 0.2, 0.4, 0.8 секунд
                        wait_time = 0.1 * (2 ** attempt)
                        logger.warning(f"⚠ База данных заблокирована для предложения #{idx+1}, попытка {attempt+1}/{max_retries}, ждем {wait_time:.2f} сек...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"✗ Не удалось обработать предложение #{idx+1} после {max_retries} попыток: database is locked")
                        return {'error': 'database is locked', 'offer_id': None}
                else:
                    # Другая ошибка - пробрасываем дальше
                    raise
            except Exception as e:
                # Другие ошибки - пробрасываем дальше
                logger.error(f"✗ Ошибка обработки предложения #{idx+1}: {e}")
                raise
    
    def process_single_offer(offer_elem, idx):
        """Обрабатывает одно предложение"""
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
            return {'error': 'no product_id', 'offer_id': None}
        
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
        
        # Продолжаем обработку товара...
        # (остальной код обработки товара)
        return {'success': True, 'offer_id': product_id}
    
    for idx, offer_elem in enumerate(offers):
        # Каждое предложение обрабатывается в отдельной транзакции с retry
        product_id = None
        # Используем retry логику для обработки ошибок "database is locked"
        max_retries = 3
        processed_successfully = False
        
        for attempt in range(max_retries):
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
                    existing_product = None  # Инициализируем переменную
                    if not product:
                        product = Product.objects.filter(external_id=product_id).first()
                    if not product:
                        product = Product.objects.filter(article=product_id).first()
                    
                    # Сохраняем найденный товар (если он есть) для возможного создания копии
                    if product:
                        existing_product = product
                    
                    # Проверяем, есть ли товар в нужном каталоге
                    product = Product.objects.filter(
                        external_id=product_id,
                        catalog_type=catalog_type
                    ).first()
                    if not product:
                        product = Product.objects.filter(
                            article=product_id,
                            catalog_type=catalog_type
                        ).first()
                    
                    # Если товар не найден в нужном каталоге, но найден в другом - создаем копию
                    if not product and existing_product:
                        # Создаем новый товар в нужном каталоге на основе найденного
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
                        # ВАЖНО: НЕ копируем изображения - оптовые товары используют изображения розничных аналогов
                        # через методы get_main_image() и get_all_images() в модели Product
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
                            # ВАЖНО: НЕ копируем изображения - оптовые товары используют изображения розничных аналогов
                            # через методы get_main_image() и get_all_images() в модели Product
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
                                # ВАЖНО: НЕ копируем изображения - оптовые товары используют изображения розничных аналогов
                                # через методы get_main_image() и get_all_images() в модели Product
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
                # ВАЖНО: Может быть несколько элементов <Количество>, суммируем их
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
                
                # Суммируем количество из всех элементов <Количество>
                # ВАЖНО: Если в XML указано количество = 0, это валидное значение (товар без остатка)
                total_quantity_from_elems = None
                found_quantity_in_xml = False
                for qty_elem in quantity_elems:
                    if qty_elem is not None and qty_elem.text:
                        try:
                            qty_value = int(float(qty_elem.text.strip().replace(',', '.')))
                            if total_quantity_from_elems is None:
                                total_quantity_from_elems = 0
                            total_quantity_from_elems += qty_value
                            found_quantity_in_xml = True
                            if idx < 5:
                                logger.info(f"Найдено количество в элементе <Количество> для товара {product_id}: {qty_value}")
                        except (ValueError, AttributeError) as e:
                            if idx < 5:
                                logger.warning(f"Не удалось распарсить остаток из <Количество> для товара {product_id}: {qty_elem.text}, ошибка: {e}")
                
                if found_quantity_in_xml:
                    # Количество найдено в XML (даже если = 0) - используем его
                    quantity = total_quantity_from_elems if total_quantity_from_elems is not None else 0
                    if idx < 5:
                        logger.info(f"✓ Общее количество из элементов <Количество> для товара {product_id}: {quantity}")
                
                # Вариант 2: Если не нашли в элементе, ищем в атрибуте <Склад КоличествоНаСкладе="..."/>
                # ВАЖНО: Может быть несколько складов, нужно суммировать количество со всех складов
                if quantity is None:
                    warehouse_elems = []
                    if namespace:
                        warehouse_elems = offer_elem.findall(f'.//{{{namespace}}}Склад')
                    if not warehouse_elems:
                        warehouse_elems = offer_elem.findall('.//Склад')
                    if not warehouse_elems and 'catalog' in namespaces:
                        try:
                            warehouse_elems = offer_elem.findall('.//catalog:Склад', namespaces)
                        except (KeyError, ValueError):
                            pass
                    
                    # Суммируем количество со всех складов
                    # ВАЖНО: Если в XML указано количество = 0, это валидное значение (товар без остатка)
                    total_warehouse_quantity = None
                    found_warehouse_quantity = False
                    for warehouse_elem in warehouse_elems:
                        # Ищем атрибут КоличествоНаСкладе
                        quantity_attr = warehouse_elem.get('КоличествоНаСкладе')
                        if not quantity_attr:
                            # Пробуем английское название атрибута
                            quantity_attr = warehouse_elem.get('QuantityInStock')
                        
                        if quantity_attr:
                            try:
                                warehouse_qty = int(float(str(quantity_attr).strip().replace(',', '.')))
                                if total_warehouse_quantity is None:
                                    total_warehouse_quantity = 0
                                total_warehouse_quantity += warehouse_qty
                                found_warehouse_quantity = True
                                if idx < 5:
                                    logger.info(f"Найдено количество на складе для товара {product_id}: {warehouse_qty} (всего складов: {len(warehouse_elems)})")
                            except (ValueError, AttributeError) as e:
                                if idx < 5:
                                    logger.warning(f"Не удалось распарсить остаток из атрибута Склад для товара {product_id}: {quantity_attr}, ошибка: {e}")
                    
                    if found_warehouse_quantity:
                        # Количество найдено в XML (даже если = 0) - используем его
                        quantity = total_warehouse_quantity if total_warehouse_quantity is not None else 0
                        if idx < 5:
                            logger.info(f"✓ Общее количество со всех складов для товара {product_id}: {quantity}")
                
                # Обновляем количество и наличие
                # ВАЖНО: Количество одинаково для обоих каталогов (retail и wholesale)
                # Разница только в ценах (price для retail, wholesale_price для wholesale)
                if quantity is not None:
                    product.quantity = quantity
                    # ВАЖНО: Синхронизируем количество с другим каталогом (retail <-> wholesale)
                    # Количество одинаково для обоих каталогов, разница только в ценах
                    if product.external_id:
                        # Находим товар в другом каталоге с тем же external_id
                        other_catalog_type = 'wholesale' if catalog_type == 'retail' else 'retail'
                        other_product = Product.objects.filter(
                            external_id=product.external_id,
                            catalog_type=other_catalog_type
                        ).first()
                        if other_product:
                            # ВАЖНО: Синхронизируем количество ТОЛЬКО если оно найдено в XML
                            # Если quantity = 0 в XML, это валидное значение - обновляем
                            # Но если quantity не найдено в XML (None), НЕ обновляем существующее количество
                            other_product.quantity = quantity
                            # Также обновляем availability для другого каталога
                            # ВАЖНО: Если quantity = 0, товар скрывается независимо от цены
                            if quantity > 0:
                                other_product.availability = 'in_stock'
                                other_product.is_active = True
                            else:
                                # Если quantity = 0, скрываем товар (независимо от цены)
                                other_product.availability = 'out_of_stock'
                                other_product.is_active = False
                            other_product.save(update_fields=['quantity', 'availability', 'is_active'])
                            if idx < 5:
                                logger.info(f"✓ Синхронизировано количество для товара {product_id} в каталоге {other_catalog_type}: {quantity}")
                    
                    # ВАЖНО: Определяем активность на основе количества
                    # Если количество > 0, товар активен и в наличии
                    # Если количество = 0, товар скрыт (неактивен) - независимо от цены
                    if quantity > 0:
                        product.availability = 'in_stock'
                        product.is_active = True  # Товар с количеством > 0 - всегда активен
                    else:
                        # Если количество = 0, скрываем товар (независимо от цены)
                        product.availability = 'out_of_stock'
                        product.is_active = False  # Товар с количеством = 0 - скрываем
                        if idx < 5:
                            logger.info(f"⚠ Товар {product_id} скрыт (количество=0)")
                    
                    # ВАЖНО: Сохраняем товар после обновления активности
                    product.save(update_fields=['quantity', 'availability', 'is_active'])
                    
                    if idx < 5:
                        if catalog_type == 'wholesale':
                            current_price = product.wholesale_price
                        else:
                            current_price = product.price
                        logger.info(f"✓ Обновлен остаток для товара {product_id}: {quantity}, наличие: {product.availability}, активен: {product.is_active}, цена: {current_price}")
                else:
                    # ВАЖНО: Если количество не найдено в XML, НЕ обновляем существующее количество
                    # Это предотвращает случайное обнуление количества при повторной обработке
                    # Товар может быть доступен под заказ, если есть цена
                    # НЕ меняем product.quantity - оставляем существующее значение
                    if idx < 10:
                        logger.warning(f"⚠ Количество не найдено в XML для товара {product_id}, оставляем существующее количество: {product.quantity}")
                    
                    # ВАЖНО: Используем существующее количество (не обнуляем)
                    # Количество одинаково для обоих каталогов
                    existing_quantity = product.quantity or 0
                    
                    # ВАЖНО: Определяем активность на основе количества
                    # Если количество > 0, товар активен и в наличии
                    # Если количество = 0, товар скрыт (неактивен) - независимо от цены
                    # Если количество не найдено в XML, используем существующее количество
                    if existing_quantity > 0:
                        product.availability = 'in_stock'
                        product.is_active = True  # Товар с количеством > 0 - всегда активен
                    else:
                        # Если количество = 0, скрываем товар (независимо от цены)
                        product.availability = 'out_of_stock'
                        product.is_active = False  # Товар с количеством = 0 - скрываем
                        if idx < 5:
                            logger.warning(f"⚠ Товар {product_id} скрыт (количество=0, количество не найдено в XML)")
                    
                    # ВАЖНО: Сохраняем товар после обновления активности
                    product.save(update_fields=['availability', 'is_active'])
                    
                    # ВАЖНО: Синхронизируем availability с другим каталогом (retail <-> wholesale)
                    # Availability должно быть одинаковым для обоих каталогов, если количество одинаково
                    if product.external_id and existing_quantity > 0:
                        # Находим товар в другом каталоге с тем же external_id
                        other_catalog_type = 'wholesale' if catalog_type == 'retail' else 'retail'
                        other_product = Product.objects.filter(
                            external_id=product.external_id,
                            catalog_type=other_catalog_type
                        ).first()
                        if other_product:
                            # Синхронизируем availability, если количество одинаково
                            if other_product.quantity == existing_quantity:
                                other_product.availability = product.availability
                                other_product.is_active = product.is_active
                                other_product.save(update_fields=['availability', 'is_active'])
                                if idx < 5:
                                    logger.info(f"✓ Синхронизировано availability для товара {product_id} в каталоге {other_catalog_type}: {product.availability}")
                    
                    if idx < 10:
                        if catalog_type == 'wholesale':
                            current_price = product.wholesale_price
                        else:
                            current_price = product.price
                        if product.is_active:
                            logger.info(f"⚠ Количество не найдено в XML для товара {product_id}, но товар активен (существующее количество: {existing_quantity}, цена: {current_price}).")
                        else:
                            logger.warning(f"⚠ Количество не найдено в XML для товара {product_id} и нет цены. Товар скрыт.")
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
                
                # Синхронизируем категорию оптового товара с розничным аналогом
                # Это гарантирует правильное распределение по категориям при каждом обмене
                if catalog_type == 'wholesale':
                    retail_counterpart = None
                    if product.external_id:
                        retail_counterpart = Product.objects.filter(
                            external_id=product.external_id,
                            catalog_type='retail'
                        ).first()
                    if not retail_counterpart and product.article:
                        retail_counterpart = Product.objects.filter(
                            article=product.article,
                            catalog_type='retail'
                        ).first()
                    if retail_counterpart and retail_counterpart.category_id != product.category_id:
                        product.category = retail_counterpart.category
                        if idx < 10:
                            logger.info(f"  ↳ Синхронизирована категория оптового товара {product_id}: {retail_counterpart.category}")
                
                product.save()
                
                # ВАЖНО: Добавляем external_id в список обработанных для логики скрытия
                # Это предотвращает скрытие товаров из offers.xml при обработке import.xml
                if product.external_id:
                    processed_external_ids.add(str(product.external_id).strip())
                elif product_id:
                    # Если external_id не установлен, используем product_id из offers.xml
                    processed_external_ids.add(str(product_id).strip())
                
                # ВАЖНО: НЕ инвалидируем кеш при обновлении товаров из offers.xml
                # Это предотвращает изменение количества при каждом обновлении страницы
                # Кеш будет обновляться автоматически через 30 минут
                # Или при создании/удалении товаров из import.xml (force=True)
                
                processed_count += 1
                updated_count += 1
                
                # Логируем успешное обновление для первых товаров
                if idx < 10:
                    current_price = product.price if catalog_type == 'retail' else product.wholesale_price
                    logger.info(f"✓ Товар обновлен: Ид={product_id}, название={product.name[:50]}, цена={current_price}, остаток={product.quantity}, активен={product.is_active}, каталог={catalog_type}")
                
                # Успешно обработано - выходим из retry цикла
                processed_successfully = True
                break
                    
            except OperationalError as e:
                error_str = str(e).lower()
                if 'database is locked' in error_str or 'locked' in error_str:
                    if attempt < max_retries - 1:
                        # Экспоненциальная задержка: 0.1, 0.2, 0.4 секунд
                        wait_time = 0.1 * (2 ** attempt)
                        logger.warning(f"⚠ База данных заблокирована для предложения #{idx+1}, попытка {attempt+1}/{max_retries}, ждем {wait_time:.2f} сек...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"✗ Не удалось обработать предложение #{idx+1} после {max_retries} попыток: database is locked")
                        errors.append({
                            'offer_id': product_id if product_id else f'offer_{idx}',
                            'error': 'database is locked'
                        })
                        break
                else:
                    # Другая ошибка - пробрасываем дальше
                    raise
                        
            except Exception as e:
                # Исключение при обработке предложения - транзакция автоматически откатывается
                error_msg = str(e)
                logger.error(f"✗ Исключение при обработке предложения #{idx+1}: {error_msg}", exc_info=True)
                errors.append({
                    'offer_id': product_id if product_id else f'offer_{idx}',
                    'error': error_msg
                })
                # Транзакция автоматически откатывается при исключении
                # Продолжаем обработку следующего предложения
                break  # Выходим из retry цикла при любой другой ошибке
    
    processing_time = (timezone.now() - start_time).total_seconds()
    request_ip = get_client_ip(request) if request else None
    
    logger.info(f"Обработано товаров в offers.xml для каталога {catalog_type}: {len(processed_external_ids)} с external_id")
    
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
    
    # ВАЖНО: Проверяем существование таблицы SyncLog перед использованием
    from django.db import connection
    table_exists = False
    try:
        with connection.cursor() as cursor:
            if 'sqlite' in connection.vendor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_synclog'")
            else:
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name='catalog_synclog'")
            table_exists = cursor.fetchone() is not None
    except Exception:
        pass
    
    if table_exists:
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
        'errors': len(errors),
        'processed_external_ids': processed_external_ids.copy()  # Сохраняем для возможного использования
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
            # ВАЖНО: Если external_id составной (содержит #), извлекаем базовый Ид
            # Это уже должно быть сделано в parse_commerceml_product, но проверяем на всякий случай
            # В CommerceML 2.0 товар с вариантами характеристик имеет составной Ид вида "uuid#characteristic_id"
            # Например: "13a33496-235b-4440-ab12-15b1eb281f06#4f02ca3d-c696-11f0-811a-00155d01d802"
            # Нужно использовать только базовый Ид (до #) для поиска и обновления товара
            if '#' in external_id:
                external_id = external_id.split('#')[0]
        if not external_id:
            external_id = None  # Используем None вместо пустой строки
        
        name = product_data.get('name', '').strip()
        article = product_data.get('article', '').strip()
        
        if not name:
            return None, "Отсутствует название товара", False
        
        # Парсим название для извлечения бренда, артикула и т.д.
        # ВАЖНО: Делаем это ДО проверки на наличие идентификатора, чтобы извлечь артикул из названия
        parsed = parse_product_name(name)
        
        # Используем артикул из данных или из парсинга
        # ВАЖНО: external_id НЕ должен использоваться как артикул!
        # Артикул должен быть только из поля "Артикул" в XML, "Артикул1" в характеристиках или из парсинга названия
        if not article and parsed.get('article'):
            article = parsed['article']
        
        # Проверяем наличие идентификатора (external_id или article)
        if not external_id and not article:
            return None, "Отсутствует идентификатор товара (Ид или Артикул)", False
        
        # Логируем для диагностики (только первые 3 товара)
        if hasattr(process_product_from_commerceml, '_log_count'):
            process_product_from_commerceml._log_count += 1
        else:
            process_product_from_commerceml._log_count = 1
        
        if process_product_from_commerceml._log_count <= 3:
            logger.info(f"Обработка товара: external_id={external_id}, article={article}, name={name[:50]}")
        
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
            from .models import Category as CategoryModel
            # Сначала ищем категорию напрямую по точному имени из 1С (любой уровень)
            category = CategoryModel.objects.filter(
                name__iexact=category_name,
                is_active=True
            ).first()
            if not category:
                # Если точного совпадения нет, пробуем через логику по ключевым словам
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
        # ВАЖНО: Товары из import.xml создаются АКТИВНЫМИ по умолчанию
        # Цены и количество придут из offers.xml и обновят статус товара
        # Это гарантирует, что все товары будут видны после обработки import.xml
        if catalog_type == 'wholesale':
            # В оптовом каталоге товар активен, если есть остаток ИЛИ есть оптовая цена
            # Используем price как оптовую цену (она будет установлена в wholesale_price)
            availability = 'in_stock' if quantity > 0 else ('order' if price > 0 else 'out_of_stock')
            # ВАЖНО: Создаем товар активным по умолчанию (цены/количество придут из offers.xml)
            is_active = True  # Всегда активен при создании из import.xml
        else:
            # В розничном каталоге товар активен, если есть цена (может быть под заказ) или есть остаток
            # ВАЖНО: Товар должен быть активен, если есть остаток ИЛИ есть цена (даже если остаток 0)
            availability = 'in_stock' if quantity > 0 else ('order' if price > 0 else 'out_of_stock')
            # ВАЖНО: Создаем товар активным по умолчанию (цены/количество придут из offers.xml)
            is_active = True  # Всегда активен при создании из import.xml
        
        # Ищем товар по external_id или по артикулу в нужном типе каталога
        # ВАЖНО: 1С может давать новое Ид одному и тому же товару, поэтому поиск по артикулу имеет приоритет
        # ВАЖНО: В CommerceML 2.0 товар с вариантами характеристик имеет составной Ид вида "uuid#characteristic_id"
        # Мы извлекаем базовый Ид (до #) и используем его для поиска товара
        # Это позволяет обновлять один товар при наличии нескольких вариантов характеристик
        product = None
        from django.db.models import Q
        
        # ВАЖНО: Сначала ищем по артикулу (если он есть), так как 1С может давать новое Ид одному и тому же товару
        # Артикул более стабилен и не меняется при обновлении товара в 1С
        if article and article.strip():
            article = article.strip()  # Нормализуем артикул
            # ВАЖНО: В базе могут быть ДУБЛИКАТЫ по артикулу в одном и том же каталоге.
            # Тогда .first() даёт случайный товар → обновляется "не тот", а на сайте открывается другой по slug.
            # Поэтому:
            # - выбираем "правильный" товар (предпочтительно по external_id из 1С)
            # - удаляем остальные дубликаты в этом catalog_type
            candidates = list(Product.objects.filter(article=article, catalog_type=catalog_type))
            if not candidates:
                # Если не нашли в нужном типе каталога, ищем в любом каталоге (редкий fallback)
                candidates = list(Product.objects.filter(article=article))
            if candidates:
                # Выбор целевого товара
                product = None
                if external_id:
                    ext = external_id.strip()
                    for p in candidates:
                        if p.external_id == ext or (p.external_id and p.external_id.startswith(ext + '#')):
                            product = p
                            break
                if not product:
                    # fallback: берём самый "свежий" по updated_at/id
                    product = sorted(
                        candidates,
                        key=lambda p: (getattr(p, 'updated_at', None) is not None, getattr(p, 'updated_at', None) or 0, p.id),
                        reverse=True
                    )[0]
                
                # Удаляем остальные дубликаты в этом каталоге (чтобы дальше обновлялся один товар)
                duplicates = [p for p in candidates if p.id != product.id and p.catalog_type == catalog_type]
                if duplicates:
                    logger.warning(
                        f"⚠ Найдены дубликаты по артикулу {article} (catalog_type={catalog_type}): "
                        f"оставляем id={product.id}, удаляем {len(duplicates)} шт: {[p.id for p in duplicates][:10]}"
                    )
                    for dup in duplicates:
                        try:
                            dup.delete()
                        except Exception as e:
                            logger.error(f"Не удалось удалить дубликат товара id={dup.id}: {e}", exc_info=True)
                
                if process_product_from_commerceml._log_count <= 3:
                    logger.info(f"✓ Товар найден по артикулу {article}: {product.name[:50]}")
                    logger.info(f"  Текущие данные товара:")
                    logger.info(f"    external_id: {product.external_id}")
                    logger.info(f"    article: {product.article}")
                    logger.info(f"    name: {product.name[:80]}")
                    logger.info(f"    body: {product_data.get('body', 'НЕТ')}")
                    logger.info(f"    characteristics: {len(product_data.get('characteristics', []))} шт.")
                    logger.info(f"  Данные из 1С:")
                    logger.info(f"    external_id: {external_id}")
                    logger.info(f"    article: {article}")
                    logger.info(f"    name: {name[:80]}")
                    logger.info(f"    body: {product_data.get('body', 'НЕТ')}")
                    logger.info(f"    characteristics: {len(product_data.get('characteristics', []))} шт.")
                # ВАЖНО: Если нашли товар по артикулу, обновляем external_id на новый из 1С
                # Это позволяет связать товар с новым Ид из 1С
                # НО: Проверяем, не используется ли новый external_id другим товаром
                if external_id and external_id.strip():
                    new_external_id = external_id.strip()
                    old_external_id = product.external_id
                    
                    # Проверяем, не используется ли новый external_id другим товаром в том же каталоге
                    if new_external_id != old_external_id:
                        conflicting_product = Product.objects.filter(
                            external_id=new_external_id,
                            catalog_type=catalog_type
                        ).exclude(pk=product.pk).first()
                        
                        if conflicting_product:
                            # Если другой товар уже использует этот external_id, это дубликат
                            # Объединяем данные: удаляем конфликтующий товар и обновляем текущий
                            if process_product_from_commerceml._log_count <= 3:
                                logger.warning(f"  ⚠ Найден конфликт: external_id {new_external_id} уже используется товаром {conflicting_product.pk}")
                                logger.warning(f"  → Удаляем дубликат и обновляем текущий товар")
                            # Удаляем конфликтующий товар (это дубликат)
                            conflicting_product.delete()
                        
                        # Обновляем external_id на новый из 1С
                        product.external_id = new_external_id
                        if process_product_from_commerceml._log_count <= 3 and old_external_id != new_external_id:
                            logger.info(f"  Будет обновлен external_id с {old_external_id} на {new_external_id}")
                # ВАЖНО: Если товар найден по артикулу, НЕ ищем по external_id дальше
                # Товар уже найден и будет обновлен, не нужно искать еще раз
                # Это предотвращает перезапись переменной product другим товаром
                skip_external_id_search = True
            else:
                skip_external_id_search = False
        else:
            skip_external_id_search = False
        
        # Если не нашли по артикулу, ищем по external_id
        if not skip_external_id_search and not product and external_id:
            # ВАЖНО: Ищем товары, у которых external_id начинается с базового Ид
            # Это позволяет найти товары, созданные с составным Ид (например, "base_id#variant_id")
            # или с базовым Ид (например, "base_id")
            # Используем Q объекты для более гибкого поиска
            
            # Ищем товары, у которых external_id точно равен базовому Ид
            # ИЛИ external_id начинается с базового Ид и содержит #
            # Это покрывает оба случая: товары с базовым Ид и товары с составным Ид
            product = Product.objects.filter(
                Q(external_id=external_id) | Q(external_id__startswith=external_id + '#'),
                catalog_type=catalog_type
            ).first()
            
            # Если не нашли в нужном типе каталога, ищем в любом каталоге
            if not product:
                product = Product.objects.filter(
                    Q(external_id=external_id) | Q(external_id__startswith=external_id + '#')
                ).first()
            
            # Если нашли товар с составным Ид, обновляем external_id на базовый Ид для единообразия
            if product and product.external_id and '#' in product.external_id:
                if process_product_from_commerceml._log_count <= 3:
                    logger.info(f"✓ Найден товар с составным Ид {product.external_id}, обновляем на базовый Ид {external_id}")
                product.external_id = external_id
                product.save(update_fields=['external_id'])
            
            # Логируем результат поиска для диагностики
            if process_product_from_commerceml._log_count <= 3:
                if product:
                    logger.info(f"✓ Товар найден по external_id={external_id}: {product.article} - {product.name[:50]}")
                else:
                    logger.info(f"⚠ Товар не найден по external_id={external_id}, будет создан новый")
        
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
            # ВАЖНО: Всегда обновляем ВСЕ данные из 1С, даже если они уже были установлены
            # Это позволяет синхронизировать любые изменения из 1С
            
            # Логируем обновление товара (только первые 3 товара)
            if process_product_from_commerceml._log_count <= 3:
                old_name = product.name[:50] if product.name else ''
                old_article = product.article or ''
                old_external_id = product.external_id or ''
                new_name = clean_name[:50] if clean_name else (name[:50] if name else '')
                new_article = article or ''
                new_external_id = external_id or ''
                logger.info(f"ОБНОВЛЕНИЕ товара: external_id={new_external_id}, article={new_article}")
                logger.info(f"  Старое название: {old_name}")
                logger.info(f"  Новое название: {new_name}")
                logger.info(f"  Старый артикул: {old_article}")
                logger.info(f"  Новый артикул: {new_article}")
                logger.info(f"  Старый external_id: {old_external_id}")
                logger.info(f"  Новый external_id: {new_external_id}")
                if old_name != new_name or old_article != new_article or old_external_id != new_external_id:
                    logger.info(f"  → БУДУТ ОБНОВЛЕНЫ: название={old_name != new_name}, артикул={old_article != new_article}, external_id={old_external_id != new_external_id}")
            
            # ВАЖНО: Всегда обновляем external_id из данных 1С
            # Но проверяем, не используется ли новый external_id другим товаром
            if external_id and external_id.strip():
                new_external_id = external_id.strip()
                old_external_id = product.external_id
                
                # Проверяем, не используется ли новый external_id другим товаром в том же каталоге
                if new_external_id != old_external_id:
                    conflicting_product = Product.objects.filter(
                        external_id=new_external_id,
                        catalog_type=catalog_type
                    ).exclude(pk=product.pk).first()
                    
                    if conflicting_product:
                        # Если другой товар уже использует этот external_id, это дубликат
                        # Объединяем данные: удаляем конфликтующий товар и обновляем текущий
                        if process_product_from_commerceml._log_count <= 3:
                            logger.warning(f"  ⚠ Найден конфликт при обновлении: external_id {new_external_id} уже используется товаром {conflicting_product.pk}")
                            logger.warning(f"  → Удаляем дубликат и обновляем текущий товар")
                        # Удаляем конфликтующий товар (это дубликат)
                        conflicting_product.delete()
                    
                    # Обновляем external_id на новый из 1С
                    product.external_id = new_external_id
            # ВАЖНО: Всегда обновляем артикул из данных 1С, даже если он пустой
            # Это позволяет синхронизировать изменения артикула из 1С (включая удаление)
            if article:
                product.article = article
            elif 'article' in product_data:
                # Если артикул явно указан в данных (даже если пустой), обновляем его
                product.article = product_data.get('article', '').strip()
            # Если артикул не указан в данных, оставляем существующий (не удаляем)
            # ВАЖНО: Всегда обновляем название товара из 1С, даже если оно уже было установлено
            # Это позволяет синхронизировать изменения названий из 1С
            # Обновляем название ВСЕГДА из данных 1С, чтобы синхронизировать изменения
            # ВАЖНО: Название должно обновляться ВСЕГДА из исходного name из XML
            # Приоритет: исходное name из XML (чтобы сохранить все данные из 1С)
            old_name_value = product.name
            if name and name.strip():
                # Используем исходное name из XML - это гарантирует, что все данные из 1С сохраняются
                product.name = name.strip()
                if process_product_from_commerceml._log_count <= 3 and old_name_value != name.strip():
                    logger.info(f"  ✓ Название обновлено: '{old_name_value[:50]}' -> '{name.strip()[:50]}'")
            elif clean_name and clean_name.strip():
                # Если name пустой, используем clean_name
                product.name = clean_name.strip()
                if process_product_from_commerceml._log_count <= 3 and old_name_value != clean_name.strip():
                    logger.info(f"  ✓ Название обновлено (clean_name): '{old_name_value[:50]}' -> '{clean_name.strip()[:50]}'")
            elif product_data.get('name'):
                # Если и name и clean_name пустые, используем name из product_data
                new_name_value = product_data.get('name', '').strip()
                product.name = new_name_value
                if process_product_from_commerceml._log_count <= 3 and old_name_value != new_name_value:
                    logger.info(f"  ✓ Название обновлено (product_data): '{old_name_value[:50]}' -> '{new_name_value[:50]}'")
            # ВАЖНО: Название должно обновляться ВСЕГДА при обновлении товара
            product.brand = brand or ''  # Всегда строка, не None
            # Обновляем цену только если она указана (не 0)
            # Это позволяет сохранить цену из offers.xml, если она уже была установлена
            # Для оптового каталога обновляем wholesale_price, для розничного - price
            if price > 0:
                if catalog_type == 'wholesale':
                    product.wholesale_price = price
                else:
                    product.price = price
            
            # ВАЖНО: При обновлении из import.xml НЕ меняем is_active
            # Товар должен оставаться активным, если он уже был активен
            # Цены и количество придут из offers.xml и обновят статус
            # Это гарантирует, что товары не деактивируются при обновлении из import.xml
            product.quantity = quantity
            product.availability = availability
            # НЕ меняем is_active при обновлении из import.xml - оставляем существующее значение
            # Если товар был активен, он останется активным
            # Если товар был неактивен, он останется неактивным (возможно, был скрыт вручную)
            if category:
                product.category = category
        
        # Описание (отображается как "Применимость") — заполняем из "Кузов" и "Двигатель" из 1С
        description_parts = []
        # Кузов из 1С
        if product_data.get('body'):
            body_list = product_data['body'] if isinstance(product_data['body'], list) else [product_data['body']]
            for body_item in body_list:
                if body_item and body_item.strip():
                    description_parts.append(f"Кузов: {body_item.strip()}")
        # Двигатель из 1С
        if product_data.get('engine'):
            engine_list = product_data['engine'] if isinstance(product_data['engine'], list) else [product_data['engine']]
            for engine_item in engine_list:
                if engine_item and engine_item.strip():
                    description_parts.append(f"Двигатель: {engine_item.strip()}")
        # ВАЖНО: Всегда обновляем описание из данных 1С, даже если оно пустое
        # Это позволяет синхронизировать изменения описания из 1С
        if description_parts:
            product.description = '\n'.join(description_parts)
        elif product_data.get('description'):
            product.description = product_data.get('description')
        else:
            # Если описание пустое в 1С, очищаем его на сайте
            product.description = ''
        
        # Применимость - используем из парсинга или из данных
        # ВАЖНО: Артикулы НЕ должны попадать в применимость!
        applicability = None
        applicability_parts = []
        
        # Добавляем "Кузов" и "Двигатель" в применимость для всех типов каталогов
        # Кузов из 1С
        if product_data.get('body'):
            body_list = product_data['body'] if isinstance(product_data['body'], list) else [product_data['body']]
            for body_item in body_list:
                if body_item and body_item.strip():
                    applicability_parts.append(body_item.strip())
        # Двигатель из 1С
        if product_data.get('engine'):
            engine_list = product_data['engine'] if isinstance(product_data['engine'], list) else [product_data['engine']]
            for engine_item in engine_list:
                if engine_item and engine_item.strip():
                    applicability_parts.append(engine_item.strip())
        
        # Если applicability пришёл как список (из характеристик)
        if product_data.get('applicability'):
            if isinstance(product_data.get('applicability'), list):
                applicability_parts.extend(product_data.get('applicability'))
            else:
                applicability_parts.append(product_data.get('applicability'))
        
        # Добавляем из парсинга (может быть строка с разделителями)
        if parsed.get('applicability'):
            parsed_applicability = parsed.get('applicability')
            # Если это строка, разбиваем по запятым
            if isinstance(parsed_applicability, str):
                parsed_parts = [p.strip() for p in parsed_applicability.split(',') if p.strip()]
                applicability_parts.extend(parsed_parts)
            elif isinstance(parsed_applicability, list):
                applicability_parts.extend(parsed_applicability)
            else:
                applicability_parts.append(str(parsed_applicability))
        
        # Извлекаем модели машин из скобок в названии
        # Пример: "Датчик кислородный (TOYOTA, 89467-71020, 2UZFE/1GRFE)" -> извлечь 2UZFE, 1GRFE
        import re
        bracket_matches = re.findall(r'\(([^)]+)\)', clean_name)
        for bracket_content in bracket_matches:
            # Разбиваем содержимое скобок по запятым
            parts = [p.strip() for p in bracket_content.split(',')]
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                
                # Пропускаем артикулы, начинающиеся с "/" (например, /EW80A - это Артикул2)
                if part.startswith('/'):
                    continue
                
                # Пропускаем артикулы (OEM номера типа 89467-71020)
                if re.match(r'^\d{5}-\d{5}$', part) or re.match(r'^\d{1}-\d{5}-\d{3}-\d{1}$', part) or re.match(r'^\d{5}-\d{3}$', part):
                    continue
                
                # Пропускаем бренды (TOYOTA, DENSO и т.д.) - они не являются применимостью
                known_brands = ['TOYOTA', 'DENSO', 'NGK', 'BOSCH', 'HONDA', 'NISSAN', 'MAZDA', 'MITSUBISHI', 'SUBARU', 'SUZUKI', 'ISUZU', 'TOYO', 'GMB', 'FEBEST']
                if part.upper() in known_brands:
                    continue
                
                # Ищем коды моделей/двигателей/кузова (формат: 2UZFE, 1GRFE, 1MZFE, 2RZ, 3RZ, ZVW30, NHW30 и т.д.)
                # Паттерн 1: цифра + буквы + (опционально) цифры + (опционально) буквы (2UZFE, 1GRFE)
                # Паттерн 2: буквы + цифры (ZVW30, NHW30, J10) - коды кузова и модели
                engine_model_pattern1 = r'^(\d+[A-Z]{2,5}(?:\d+[A-Z]{0,3})?)$'  # 2UZFE, 1GRFE
                engine_model_pattern2 = r'^([A-Z]{2,5}\d+[A-Z0-9]{0,3})$'  # ZVW30, NHW30, J10
                if re.match(engine_model_pattern1, part, re.IGNORECASE) or re.match(engine_model_pattern2, part, re.IGNORECASE):
                    # Это код модели/двигателя/кузова - добавляем в применимость
                    if part.upper() not in [p.upper() for p in applicability_parts]:
                        applicability_parts.append(part.upper())
                    continue
                
                # Ищем связки через слеш (например, 2UZFE/1GRFE, 2RZ/3RZ, J10/RH)
                if '/' in part:
                    slash_parts = [p.strip() for p in part.split('/')]
                    for slash_part in slash_parts:
                        if re.match(engine_model_pattern1, slash_part, re.IGNORECASE) or re.match(engine_model_pattern2, slash_part, re.IGNORECASE):
                            if slash_part.upper() not in [p.upper() for p in applicability_parts]:
                                applicability_parts.append(slash_part.upper())
                        # Также проверяем, может быть это связка кодов двигателей (2RZ/3RZ)
                        elif re.match(r'^\d+[A-Z]{2,5}$', slash_part, re.IGNORECASE):
                            if slash_part.upper() not in [p.upper() for p in applicability_parts]:
                                applicability_parts.append(slash_part.upper())
                        # Проверяем коды кузова/модели (ZVW30, J10, RH)
                        elif re.match(r'^[A-Z]{2,5}\d+[A-Z0-9]{0,3}$', slash_part, re.IGNORECASE) or re.match(r'^[A-Z]{1,3}\d+$', slash_part, re.IGNORECASE):
                            if slash_part.upper() not in [p.upper() for p in applicability_parts]:
                                applicability_parts.append(slash_part.upper())
        
        # ВАЖНО: TIS-166/GUIS-66 - это ПРИМЕНИМОСТЬ, не артикул!
        # Артикул = OEM номер (кросс-номер)
        # Применимость может содержать артикулы альтернативные (TIS-166, GUIS-66) - это нормально
        # Убираем дубликаты и фильтруем пустые значения
        # ВАЖНО: Исключаем артикулы (значения, начинающиеся с "/") из применимости
        unique_applicability = []
        seen = set()
        for p in applicability_parts:
            if p and str(p).strip():
                p_str = str(p).strip()
                # Пропускаем артикулы, начинающиеся с "/" (например, /EW80A - это Артикул2)
                if p_str.startswith('/'):
                    continue
                p_upper = p_str.upper()
                if p_upper not in seen:
                    seen.add(p_upper)
                    unique_applicability.append(p_str)
        
        # Извлекаем вольтаж из применимости и переносим в характеристики
        # ВАЖНО: Вольтаж (12V, 24V и т.д.) должен быть в характеристиках, а не в применимости!
        voltage_from_applicability = None
        if unique_applicability:
            # Проверяем, есть ли вольтаж в применимости
            import re
            voltage_pattern = re.compile(r'\b(\d+V(?:-\d+V)?)\b', re.IGNORECASE)
            filtered_applicability = []
            for item in unique_applicability:
                voltage_match = voltage_pattern.search(item)
                if voltage_match:
                    # Найден вольтаж - извлекаем его и не добавляем в применимость
                    voltage_from_applicability = voltage_match.group(1).upper()
                else:
                    # Это не вольтаж - добавляем в применимость
                    filtered_applicability.append(item)
            unique_applicability = filtered_applicability
        
        # ВАЖНО: Всегда обновляем применимость из данных 1С, даже если она пустая
        # Это позволяет синхронизировать изменения применимости из 1С
        old_applicability = product.applicability or ''
        if unique_applicability:
            applicability = ', '.join(unique_applicability)
            product.applicability = applicability
            if process_product_from_commerceml._log_count <= 3:
                if old_applicability != applicability:
                    logger.info(f"  ✓ Применимость обновлена: '{old_applicability[:80]}' -> '{applicability[:80]}'")
                else:
                    logger.info(f"  → Применимость без изменений: '{applicability[:80]}'")
        else:
            # Если применимость пустая в 1С, очищаем её на сайте
            product.applicability = ''
            if process_product_from_commerceml._log_count <= 3:
                if old_applicability:
                    logger.info(f"  ✓ Применимость очищена (было: '{old_applicability[:80]}')")
                else:
                    logger.info(f"  → Применимость пустая (без изменений)")
        
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
        
        # ВАЖНО: Всегда обновляем кросс-номера из данных 1С, даже если они пустые
        # Это позволяет синхронизировать изменения кросс-номеров из 1С
        if cross_numbers_parts:
            cross_numbers = ', '.join([p for p in cross_numbers_parts if p and str(p).strip()])
            product.cross_numbers = cross_numbers
        else:
            # Если кросс-номера пустые в 1С, очищаем их на сайте
            product.cross_numbers = ''
        
        # Характеристики - объединяем из парсинга названия и из XML
        characteristics_parts = []
        
        # Сначала добавляем характеристики из парсинга названия (это более надежно)
        # ВАЖНО: Но "Размер" из XML имеет приоритет над "Размер" из парсинга названия
        import re
        excluded_materials = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
        
        # Проверяем, есть ли "Размер" в XML
        has_size_in_xml = False
        if product_data.get('characteristics'):
            char_list = product_data.get('characteristics', [])
            if isinstance(char_list, list):
                for char_data in char_list:
                    if isinstance(char_data, dict):
                        char_name = char_data.get('name', '').strip()
                        if 'размер' in char_name.lower() or 'size' in char_name.lower():
                            has_size_in_xml = True
                            break
        
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
                    
                    # Если "Размер" есть в XML, пропускаем "Размер" из парсинга названия
                    # ВАЖНО: Удаляем строки "Размер:" из парсинга, так как значение уже попало в "Характеристика:" из XML
                    if ('размер' in char_name_lower or 'size' in char_name_lower) and has_size_in_xml:
                        continue
                    
                    # Также удаляем строки "Размер:" из парсинга названия, даже если "Размер" не в XML
                    # Потому что значение должно быть только в "Характеристика:", а не в "Размер:"
                    if 'размер' in char_name_lower or 'size' in char_name_lower:
                        continue
                    
                    # ВАЖНО: Если "Размер" есть в XML, пропускаем короткие характеристики, которые могут быть частью значения "Размер"
                    # Например, "РЕМ" из "12V/140А/ПЛ. РЕМ. 6Д/ОВ.Ф/ЗКОНТ" не должна добавляться как отдельная характеристика
                    if has_size_in_xml and char_name_lower in ['характеристика', 'characteristic']:
                        # Проверяем, не является ли значение частью "Размера" из XML
                        should_skip_char = False
                        if product_data.get('characteristics'):
                            char_list = product_data.get('characteristics', [])
                            if isinstance(char_list, list):
                                for char_data in char_list:
                                    if isinstance(char_data, dict):
                                        xml_char_name = char_data.get('name', '').strip().lower()
                                        xml_char_value = char_data.get('value', '').strip()
                                        if 'размер' in xml_char_name or 'size' in xml_char_name:
                                            # Если значение из парсинга содержится в значении "Размер" из XML, пропускаем
                                            if char_value_stripped.upper() in xml_char_value.upper():
                                                should_skip_char = True
                                                break
                        if should_skip_char:
                            continue
                    
                    # Проверяем, что значение не является кодом модели/применимости
                    # Коды моделей обычно: 1-4 цифры + буквы (например, 1GEN, 1NZF, 2GR, 4AFE)
                    # Но НЕ фильтруем размеры — они всегда должны попадать в характеристики
                    if 'размер' not in char_name_lower and 'size' not in char_name_lower:
                        if re.match(r'^[A-Z0-9#\-/]{1,10}$', char_value_upper) and not re.search(r'[*x]', char_value_stripped):
                            # Это похоже на код модели, а не на характеристику - пропускаем
                            continue
                    
                    characteristics_parts.append(char_line)
        
        # Затем добавляем характеристики из XML (как список словарей)
        # ИСКЛЮЧАЕМ служебные характеристики: Артикул1, Артикул2, Марка, Двигатель
        excluded_chars = ['артикул1', 'артикул 1', 'article1', 'article 1',
                          'артикул2', 'артикул 2', 'article2', 'article 2', 'oem', 'oem номер',
                          'марка', 'brand', 'бренд',
                          'двигатель', 'engine', 'мотор',
                          'кузов', 'body', 'тип кузова']
        
        if product_data.get('characteristics'):
            char_list = product_data.get('characteristics', [])
            if isinstance(char_list, list):
                import re
                excluded_materials = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
                
                for char_data in char_list:
                    if isinstance(char_data, dict):
                        char_name = char_data.get('name', '').strip()
                        # ВАЖНО: Не используем strip() для значения, чтобы сохранить полное значение "Размер"
                        # Значение уже было правильно извлечено из XML с помощью itertext()
                        char_value = char_data.get('value', '')
                        if char_name:
                            char_name_lower = char_name.lower()
                            
                            # ВАЖНО: "Размер" всегда должен попадать в характеристики БЕЗ фильтрации!
                            # Значение может быть любым: "12V/80А/ПЛ. РЕМ.5Д/ОВ.Ф./ЗКОНТ", "20*450", "70*117*27" и т.д.
                            # Обрабатываем "Размер" ПЕРВЫМ, до всех других проверок, чтобы гарантировать попадание в характеристики
                            if 'размер' in char_name_lower or 'size' in char_name_lower:
                                # ВАЖНО: Обрабатываем "Размер" даже если значение пустое или не проходит другие проверки
                                if not char_value:
                                    char_value = ''  # Разрешаем пустое значение для "Размер"
                                # ВАЖНО: Значение "Размер" должно попадать в "Характеристика", а не создавать отдельную строку "Размер"!
                                # Логируем для отладки (только первые 3 товара)
                                if hasattr(process_product_from_commerceml, '_log_size_count'):
                                    process_product_from_commerceml._log_size_count += 1
                                else:
                                    process_product_from_commerceml._log_size_count = 1
                                if process_product_from_commerceml._log_size_count <= 3:
                                    logger.info(f"✓ Найден 'Размер' в XML: name='{char_name}', value='{char_value}' (длина={len(char_value)})")
                                
                                # Удаляем ВСЕ старые "Размер" и "Характеристика" из парсинга названия, если они есть
                                # Ищем все характеристики, которые начинаются с "Размер:", "Size:", "Характеристика:" или "Characteristic:"
                                old_count = len(characteristics_parts)
                                characteristics_parts = [
                                    c for c in characteristics_parts 
                                    if not (':' in c and (
                                        c.lower().strip().startswith('размер:') or 
                                        c.lower().strip().startswith('size:') or
                                        c.lower().strip().startswith('характеристика:') or
                                        c.lower().strip().startswith('characteristic:')
                                    ))
                                ]
                                removed_count = old_count - len(characteristics_parts)
                                if removed_count > 0 and process_product_from_commerceml._log_size_count <= 3:
                                    logger.info(f"  Удалено {removed_count} старых 'Размер'/'Характеристика' из парсинга названия")
                                
                                # Добавляем значение из "Размер" в "Характеристика" (не создаем строку "Размер"!)
                                char_str = f"Характеристика: {char_value}"
                                characteristics_parts.append(char_str)
                                if process_product_from_commerceml._log_size_count <= 3:
                                    logger.info(f"  Добавлено значение из 'Размер' в 'Характеристика': '{char_str}'")
                                continue
                            
                            # Пропускаем служебные характеристики
                            if char_name_lower in excluded_chars:
                                continue
                            
                            # Пропускаем материалы
                            if any(material in char_name_lower for material in excluded_materials):
                                continue
                            
                            # Для остальных характеристик проверяем, что значение не пустое и не является кодом модели/применимости
                            if not char_value:
                                continue
                            
                            char_value_upper = char_value.upper()
                            # Коды моделей обычно: 1-4 цифры + буквы (например, 1GEN, 1NZF, 2GR, 4AFE)
                            if re.match(r'^[A-Z0-9#\-/]{1,10}$', char_value_upper) and not re.search(r'[*x]', char_value):
                                # Это похоже на код модели, а не на характеристику - пропускаем
                                continue
                            
                            # Добавляем характеристику
                            char_str = f"{char_name}: {char_value}"
                            # Проверяем, нет ли уже такой характеристики
                            if not any(char_str in existing for existing in characteristics_parts):
                                characteristics_parts.append(char_str)
        
        # Добавляем вольтаж из применимости в характеристики (если он был найден)
        if voltage_from_applicability:
            voltage_char = f"Напряжение: {voltage_from_applicability}"
            # Проверяем, нет ли уже такой характеристики
            if not any('Напряжение:' in char and voltage_from_applicability in char for char in characteristics_parts):
                characteristics_parts.append(voltage_char)
        
        # Также проверяем, есть ли вольтаж в уже сохраненной применимости товара
        if product.applicability:
            voltage_match = re.search(r'\b(\d+V(?:-\d+V)?)\b', product.applicability, re.IGNORECASE)
            if voltage_match:
                voltage_value = voltage_match.group(1).upper()
                voltage_char = f"Напряжение: {voltage_value}"
                # Проверяем, нет ли уже такой характеристики
                if not any('Напряжение:' in char and voltage_value in char for char in characteristics_parts):
                    characteristics_parts.append(voltage_char)
        
        # Объединяем все характеристики
        # ВАЖНО: Всегда обновляем характеристики при импорте из XML, чтобы исправить неправильные значения
        # ВАЖНО: Обновляем характеристики ВСЕГДА из данных 1С, даже если они пустые
        # Это позволяет синхронизировать изменения характеристик из 1С
        old_characteristics = product.characteristics or ''
        if characteristics_parts:
            new_characteristics = '\n'.join(characteristics_parts)
            # Логируем изменение характеристик для отладки (только первые 3 товара)
            if hasattr(process_product_from_commerceml, '_log_char_update_count'):
                process_product_from_commerceml._log_char_update_count += 1
            else:
                process_product_from_commerceml._log_char_update_count = 1
            if process_product_from_commerceml._log_char_update_count <= 3:
                logger.info(f"Обновление характеристик товара {product.external_id or product.article}:")
                logger.info(f"  Старые: '{old_characteristics[:100]}...' (длина={len(old_characteristics)})")
                logger.info(f"  Новые: '{new_characteristics[:100]}...' (длина={len(new_characteristics)})")
                if old_characteristics != new_characteristics:
                    logger.info(f"  ✓ Характеристики будут обновлены")
                else:
                    logger.info(f"  → Характеристики без изменений")
            product.characteristics = new_characteristics
        else:
            # ВАЖНО: Если характеристики пустые в 1С, очищаем их на сайте
            # Это позволяет синхронизировать изменения характеристик из 1С
            product.characteristics = ''
            if process_product_from_commerceml._log_count <= 3:
                if old_characteristics:
                    logger.info(f"  ✓ Характеристики очищены (было: '{old_characteristics[:100]}...')")
                else:
                    logger.info(f"  → Характеристики пустые (без изменений)")
        
        # ВАЖНО: Сохраняем товар ПЕРЕД обработкой ProductCharacteristic
        # Это гарантирует, что товар будет создан даже если ProductCharacteristic не работает
        try:
            # ВАЖНО: При обновлении товара принудительно сохраняем все поля
            # Используем save() без update_fields, чтобы гарантировать сохранение ВСЕХ полей
            product.save()
            
            # ВАЖНО: Инвалидируем кеш при создании И при обновлении товара
            # Это гарантирует, что изменения сразу отображаются на сайте
            if product.category:
                invalidate_category_cache(product.category, force=True)
            
            if was_created:
                logger.info(f"✓ Товар сохранен в БД: {product.external_id or product.article} (catalog_type={catalog_type})")
            else:
                if process_product_from_commerceml._log_count <= 3:
                    logger.info(f"✓ Товар обновлен в БД: {product.external_id or product.article} - {product.name[:50]}")
                    logger.info(f"  Проверка сохраненных данных:")
                    logger.info(f"    external_id: {product.external_id}")
                    logger.info(f"    article: {product.article}")
                    logger.info(f"    name: {product.name[:80]}")
                    logger.info(f"    applicability: {product.applicability[:100] if product.applicability else 'ПУСТО'}")
                    logger.info(f"    description: {product.description[:100] if product.description else 'ПУСТО'}")
                    logger.info(f"    characteristics: {product.characteristics[:100] if product.characteristics else 'ПУСТО'}")
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
