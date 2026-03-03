"""
URL configuration for the catalog project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse, FileResponse, Http404
import os
import mimetypes
from catalog.sitemaps import ProductSitemap, CategorySitemap, StaticViewSitemap
from catalog.admin_views import (
    bulk_image_upload, 
    bulk_product_import, 
    quick_add_product,
    download_import_template,
)
from partners.admin_views import (
    bulk_wholesale_import,
    download_wholesale_template,
)
from catalog import commerceml_views
from catalog import farpost_views
from catalog import views as catalog_views

sitemaps = {
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
}

def serve_static_file(request, path):
    """
    Раздача статических файлов через Django view (для DEBUG=False).
    Работает как fallback, если nginx не настроен.
    Query string параметры (например, ?v=2.7) игнорируются - они используются только для кеширования.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Логируем начало обработки запроса
    logger.info(f"=== STATIC FILE REQUEST: {request.path} ===")
    logger.info(f"Original path parameter: {path}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"DEBUG setting: {settings.DEBUG}")
    
    # Убираем query string из path, если он есть (Django обычно передает path без query string)
    # Но на всякий случай проверяем
    if '?' in path:
        path = path.split('?')[0]
        logger.info(f"Removed query string, new path: {path}")
    
    # Пытаемся найти файл в STATIC_ROOT
    static_root = str(settings.STATIC_ROOT)
    file_path = os.path.join(static_root, path)
    
    # Нормализуем пути
    static_root = os.path.abspath(static_root)
    file_path = os.path.abspath(file_path)
    
    logger.info(f"Serving static file: path={path}, file_path={file_path}, exists={os.path.exists(file_path)}")
    
    # Проверяем существование файла
    if os.path.exists(file_path) and os.path.isfile(file_path):
        # Проверяем безопасность пути
        if not file_path.startswith(static_root):
            logger.warning(f"Invalid path attempt: {file_path} (not in {static_root})")
            raise Http404("Invalid path")
        
        # Определяем MIME type
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            # Определяем по расширению вручную
            if path.endswith('.css'):
                content_type = 'text/css; charset=utf-8'
            elif path.endswith('.js'):
                content_type = 'application/javascript; charset=utf-8'
            else:
                content_type = 'application/octet-stream'
        
        try:
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            response['Cache-Control'] = 'public, max-age=31536000'
            logger.info(f"Successfully serving file: {file_path} (Content-Type: {content_type})")
            return response
        except Exception as e:
            logger.error(f"Error serving file {file_path}: {e}", exc_info=True)
            raise Http404(f"Error serving file: {path}")
    
    # Если не нашли в STATIC_ROOT, пробуем STATICFILES_DIRS
    if settings.STATICFILES_DIRS and len(settings.STATICFILES_DIRS) > 0:
        static_dir = str(settings.STATICFILES_DIRS[0])
        file_path = os.path.join(static_dir, path)
        static_dir = os.path.abspath(static_dir)
        file_path = os.path.abspath(file_path)
        
        logger.info(f"Trying STATICFILES_DIRS: path={path}, file_path={file_path}, exists={os.path.exists(file_path)}")
        
        # Проверяем существование файла
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Проверяем безопасность пути
            if not file_path.startswith(static_dir):
                logger.warning(f"Invalid path attempt: {file_path} (not in {static_dir})")
                raise Http404("Invalid path")
            
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                # Определяем по расширению вручную
                if path.endswith('.css'):
                    content_type = 'text/css; charset=utf-8'
                elif path.endswith('.js'):
                    content_type = 'application/javascript; charset=utf-8'
                else:
                    content_type = 'application/octet-stream'
            
            try:
                response = FileResponse(open(file_path, 'rb'), content_type=content_type)
                response['Cache-Control'] = 'public, max-age=31536000'
                logger.info(f"Successfully serving file from STATICFILES_DIRS: {file_path} (Content-Type: {content_type})")
                return response
            except Exception as e:
                logger.error(f"Error serving file {file_path}: {e}", exc_info=True)
                raise Http404(f"Error serving file: {path}")
    
    logger.warning(f"Static file not found: {path} (tried {os.path.join(static_root, path)} and {os.path.join(str(settings.STATICFILES_DIRS[0]), path) if settings.STATICFILES_DIRS else 'N/A'})")
    raise Http404(f"File not found: {path}")

urlpatterns = [
    # ВАЖНО: Статика должна быть ПЕРВОЙ, чтобы не перехватывалась другими паттернами
    # Это особенно важно при DEBUG=False, когда используется кастомный view
    # (при DEBUG=True staticfiles_urlpatterns добавляется в конец, но имеет приоритет)
    
    # Стандартный протокол CommerceML 2 обмена с 1С (ОБЯЗАТЕЛЬНО ПЕРВЫМ после статики!)
    # ВАЖНО: Эти пути должны быть в самом начале списка для правильной работы
    path('cml/exchange/', commerceml_views.commerceml_exchange, name='commerceml_exchange'),
    path('cml/exchange', commerceml_views.commerceml_exchange, name='commerceml_exchange_no_slash'),  # Без слэша для совместимости
    path('1c_exchange.php', commerceml_views.commerceml_exchange, name='commerceml_exchange_php'),
    
    # Тестовый endpoint для проверки доступности
    path('cml/test/', lambda r: HttpResponse('OK - CommerceML endpoint доступен', content_type='text/plain; charset=utf-8'), name='commerceml_test'),
    
    # API для 1С
    path('api/1c/', include('catalog.api_urls')),
    
    # Прайс-лист для Farpost (автоматическое обновление)
    # Farpost загружает этот файл периодически по указанной ссылке
    re_path(r'^farpost/price-list\.(csv|xls|xml)$', farpost_views.farpost_price_list, name='farpost_price_list'),
    
    # Кастомные админ-страницы (до admin/)
    path('admin/catalog/bulk-images/', bulk_image_upload, name='admin_bulk_image_upload'),
    path('admin/catalog/bulk-import/', bulk_product_import, name='admin_bulk_product_import'),
    path('admin/catalog/quick-add/', quick_add_product, name='admin_quick_add_product'),
    path('admin/catalog/import-template/', download_import_template, name='admin_download_import_template'),
    
    # Партнёрский импорт (оптовые товары)
    path('admin/partners/bulk-import/', bulk_wholesale_import, name='admin_bulk_wholesale_import'),
    path('admin/partners/wholesale-template/', download_wholesale_template, name='admin_download_wholesale_template'),
    
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('catalog/', include('catalog.urls')),
    path('orders/', include('orders.urls')),
    path('partners/', include('partners.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    
    # Редирект со старых URL /items/ на новые /catalog/product/
    re_path(r'^items/(?P<slug>[\w-]+)/$', catalog_views.redirect_old_item_url, name='redirect_old_item'),
]

# Раздача статических файлов
# При DEBUG=True используем стандартный механизм Django (django.contrib.staticfiles)
# При DEBUG=False используем кастомный view (fallback, если nginx не настроен)
# ВАЖНО: Паттерн для статики должен быть ПЕРВЫМ в списке, чтобы не перехватывался другими маршрутами
if settings.DEBUG:
    # DEBUG=True: используем стандартный механизм Django для разработки
    # Это автоматически обрабатывает STATICFILES_DIRS и STATIC_ROOT
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    # Добавляем в начало, чтобы иметь приоритет
    urlpatterns = staticfiles_urlpatterns() + urlpatterns
else:
    # DEBUG=False: используем кастомный view для продакшена (если nginx не настроен)
    # ВАЖНО: В продакшене предпочтительно использовать nginx для раздачи статики
    # Этот view работает как fallback, если nginx не настроен или не работает
    # ВАЖНО: Добавляем в НАЧАЛО списка для приоритета!
    urlpatterns = [
        re_path(r'^static/(?P<path>.*)$', serve_static_file, name='serve_static'),
    ] + urlpatterns

# Раздача медиа-файлов (работает и на продакшене)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

