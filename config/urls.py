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
    """Раздача статических файлов через Django view (работает при любом DEBUG)"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Логируем, что view вызван
    logger.warning(f"=== SERVE_STATIC_FILE CALLED: path={path} ===")
    
    # Пытаемся найти файл в STATIC_ROOT
    static_root = str(settings.STATIC_ROOT)
    file_path = os.path.join(static_root, path)
    
    # Нормализуем пути
    static_root = os.path.abspath(static_root)
    file_path = os.path.abspath(file_path)
    
    logger.warning(f"Serve static: path={path}, static_root={static_root}, file_path={file_path}, exists={os.path.exists(file_path)}")
    
    # Проверяем существование файла
    if os.path.exists(file_path) and os.path.isfile(file_path):
        # Проверяем безопасность пути
        if not file_path.startswith(static_root):
            raise Http404("Invalid path")
        # Определяем MIME type
        content_type = 'application/octet-stream'
        if path.endswith('.css'):
            content_type = 'text/css'
        elif path.endswith('.js'):
            content_type = 'application/javascript'
        elif path.endswith('.png'):
            content_type = 'image/png'
        elif path.endswith('.jpg') or path.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif path.endswith('.svg'):
            content_type = 'image/svg+xml'
        elif path.endswith('.webp'):
            content_type = 'image/webp'
        elif path.endswith('.woff') or path.endswith('.woff2'):
            content_type = 'font/woff2'
        elif path.endswith('.ico'):
            content_type = 'image/x-icon'
        
        logger.info(f"Found file in STATIC_ROOT: {file_path}")
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Cache-Control'] = 'public, max-age=31536000'
        return response
    
    # Если не нашли в STATIC_ROOT, пробуем STATICFILES_DIRS
    logger.info(f"File not found in STATIC_ROOT, trying STATICFILES_DIRS")
    if settings.STATICFILES_DIRS and len(settings.STATICFILES_DIRS) > 0:
        static_dir = str(settings.STATICFILES_DIRS[0])
        file_path = os.path.join(static_dir, path)
        static_dir = os.path.abspath(static_dir)
        file_path = os.path.abspath(file_path)
        
        # Проверяем существование файла
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Проверяем безопасность пути
            if not file_path.startswith(static_dir):
                raise Http404("Invalid path")
            content_type = 'application/octet-stream'
            if path.endswith('.css'):
                content_type = 'text/css'
            elif path.endswith('.js'):
                content_type = 'application/javascript'
            elif path.endswith('.png'):
                content_type = 'image/png'
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif path.endswith('.svg'):
                content_type = 'image/svg+xml'
            elif path.endswith('.webp'):
                content_type = 'image/webp'
            
            logger.info(f"Found file in STATICFILES_DIRS: {file_path}")
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            response['Cache-Control'] = 'public, max-age=31536000'
            return response
    
    logger.error(f"File not found: {path} (tried {os.path.join(static_root, path)} and {os.path.join(str(settings.STATICFILES_DIRS[0]), path) if settings.STATICFILES_DIRS else 'N/A'})")
    raise Http404(f"File not found: {path}")

urlpatterns = [
    # Раздача статики через Django view (ОБЯЗАТЕЛЬНО ПЕРВЫМ!)
    # Должен быть до всех остальных путей, чтобы обрабатывать запросы к /static/
    re_path(r'^static/(?P<path>.*)$', serve_static_file, name='serve_static'),
    
    # Тестовый endpoint для проверки доступности
    path('cml/test/', lambda r: HttpResponse('OK - CommerceML endpoint доступен', content_type='text/plain; charset=utf-8'), name='commerceml_test'),
    
    # Стандартный протокол CommerceML 2 обмена с 1С (ОБЯЗАТЕЛЬНО ПЕРВЫМ!)
    # ВАЖНО: Эти пути должны быть в самом начале списка для правильной работы
    path('cml/exchange/', commerceml_views.commerceml_exchange, name='commerceml_exchange'),
    path('cml/exchange', commerceml_views.commerceml_exchange, name='commerceml_exchange_no_slash'),  # Без слэша для совместимости
    path('1c_exchange.php', commerceml_views.commerceml_exchange, name='commerceml_exchange_php'),
    
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

# Раздача медиа-файлов (работает и на продакшене)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Статика раздается через view serve_static_file (см. выше в urlpatterns)
# Работает при любом значении DEBUG

