"""
URL configuration for the catalog project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
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

sitemaps = {
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
}

urlpatterns = [
    # Кастомные админ-страницы (до admin/)
    path('admin/catalog/bulk-images/', bulk_image_upload, name='admin_bulk_image_upload'),
    path('admin/catalog/bulk-import/', bulk_product_import, name='admin_bulk_product_import'),
    path('admin/catalog/quick-add/', quick_add_product, name='admin_quick_add_product'),
    path('admin/catalog/import-template/', download_import_template, name='admin_download_import_template'),
    
    # Партнёрский импорт (оптовые товары)
    path('admin/partners/bulk-import/', bulk_wholesale_import, name='admin_bulk_wholesale_import'),
    path('admin/partners/wholesale-template/', download_wholesale_template, name='admin_download_wholesale_template'),
    
    # API для 1С
    path('api/1c/', include('catalog.api_urls')),
    
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('catalog/', include('catalog.urls')),
    path('orders/', include('orders.urls')),
    path('partners/', include('partners.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

# Раздача медиа-файлов (работает и на продакшене)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    # Раздача статических файлов через Django (только в режиме разработки)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

