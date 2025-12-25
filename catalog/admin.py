from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
from mptt.admin import DraggableMPTTAdmin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
import csv
from .models import Category, Product, ProductImage, Brand, ImportLog, OneCExchangeLog


class ProductImageInline(admin.TabularInline):
    """Инлайн для изображений товара."""
    model = ProductImage
    extra = 1
    fields = ['image', 'is_main', 'alt', 'order', 'image_preview']
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px;"/>', obj.image.url)
        return '-'
    image_preview.short_description = 'Превью'


class ProductResource(resources.ModelResource):
    """Ресурс для импорта/экспорта товаров."""
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=ForeignKeyWidget(Category, 'slug')
    )

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'article', 'brand', 'category', 'price', 'old_price',
            'condition', 'availability', 'quantity', 'short_description', 
            'description', 'characteristics', 'applicability', 'cross_numbers',
            'farpost_url', 'is_active', 'is_featured'
        )
        export_order = fields
        import_id_fields = ['article']
        skip_unchanged = True
        report_skipped = True

    def get_import_fields(self):
        """Возвращает список полей для импорта с поддержкой альтернативных названий колонок."""
        return super().get_import_fields()

    def before_import_row(self, row, **kwargs):
        """Нормализует и маппит колонки из файла клиента перед импортом."""
        # Функция для нормализации ключей колонок
        def normalize_key(key):
            if not key:
                return None
            key_lower = str(key).lower().strip()
            
            # Название товара - из колонки "Номенклатура, Характеристика. Наименование для печати"
            if any(word in key_lower for word in ['номенклатура', 'наименование', 'характеристика', 'печать', 'название']):
                return 'name'
            
            # Артикул
            if 'артикул' in key_lower or key_lower == 'article':
                return 'article'
            
            # Цена - из колонки "Розничная Фарпост RUB Не включает Цена"
            if any(word in key_lower for word in ['цена', 'розничная', 'farpost', 'руб', 'price']):
                return 'price'
            
            # Остаток - из колонки "Склад Уссурийск Остаток"
            if any(word in key_lower for word in ['остаток', 'склад', 'уссурийск', 'quantity']):
                return 'quantity'
            
            # Стандартные поля
            if key_lower in ['name', 'brand', 'category', 'description', 'applicability', 
                            'cross_numbers', 'condition', 'availability', 'short_description', 
                            'characteristics', 'old_price', 'farpost_url', 'is_active', 'is_featured']:
                return key_lower
            
            return None
        
        # Создаем новый словарь с нормализованными ключами
        normalized_row = {}
        
        # Маппим все колонки
        for key, value in row.items():
            normalized_key = normalize_key(key)
            if normalized_key:
                # Если ключ уже есть, берем первую непустую колонку
                if normalized_key not in normalized_row or not normalized_row[normalized_key]:
                    if value is not None:
                        normalized_row[normalized_key] = value
        
        # Обрабатываем числовые значения
        # Цена
        if 'price' in normalized_row:
            price_str = str(normalized_row['price']).strip()
            if price_str and price_str.lower() not in ['none', 'null', '']:
                # Убираем пробелы и заменяем запятую на точку
                price_str = price_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
                try:
                    normalized_row['price'] = float(price_str)
                except (ValueError, TypeError):
                    normalized_row['price'] = 0
        
        # Количество
        if 'quantity' in normalized_row:
            qty_str = str(normalized_row['quantity']).strip()
            if qty_str and qty_str.lower() not in ['none', 'null', '']:
                # Убираем разделители тысяч
                qty_str = qty_str.replace(' ', '').replace('\xa0', '').replace(',', '')
                try:
                    normalized_row['quantity'] = int(float(qty_str))
                except (ValueError, TypeError):
                    normalized_row['quantity'] = 0
        
        # Очистка строковых полей
        for field in ['name', 'article', 'brand', 'category', 'description', 'applicability', 
                     'cross_numbers', 'short_description', 'characteristics']:
            if field in normalized_row:
                normalized_row[field] = str(normalized_row[field]).strip() if normalized_row[field] else ''
        
        # Устанавливаем значения по умолчанию
        if 'condition' not in normalized_row or not normalized_row['condition']:
            normalized_row['condition'] = 'new'
        if 'availability' not in normalized_row or not normalized_row['availability']:
            normalized_row['availability'] = 'in_stock'
        if 'is_active' not in normalized_row:
            normalized_row['is_active'] = True
        
        # Обновляем оригинальный row (изменяем значения напрямую)
        for key in list(row.keys()):
            if key not in normalized_row:
                del row[key]
        
        for key, value in normalized_row.items():
            row[key] = value
        
        # Если нет названия, пропускаем строку
        if not row.get('name') or str(row.get('name', '')).strip().lower() in ['none', 'null', '']:
            # Устанавливаем флаг для пропуска
            row['_skip'] = True
    
    def skip_row(self, instance, original, row, import_validation_errors=None):
        """Пропускает строки без названия или с флагом _skip."""
        # Проверяем флаг пропуска из row
        if row.get('_skip'):
            return True
        # Проверяем наличие названия
        if hasattr(instance, 'name') and not instance.name:
            return True
        return super().skip_row(instance, original, row, import_validation_errors)


class FarpostExportMixin:
    """Миксин для экспорта в формат Farpost."""
    
    def export_farpost(self, request, queryset):
        """Экспорт выбранных товаров в формат Farpost согласно ТЗ."""
        from .services import (
            generate_farpost_title,
            generate_farpost_description,
            generate_farpost_images,
        )
        
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="farpost_export.csv"'
        
        writer = csv.writer(response, delimiter=';')
        # Заголовки для Farpost (расширенный формат)
        writer.writerow([
            'Заголовок', 'Цена', 'Описание', 'Артикул', 'Бренд',
            'Состояние', 'Наличие', 'Характеристики', 'Применимость',
            'Кросс-номера', 'Фото1', 'Фото2', 'Фото3', 'Фото4', 'Фото5', 
            'Ссылка на сайт', 'Категория'
        ])
        
        for product in queryset:
            # Генерируем заголовок по шаблону из ТЗ
            title = generate_farpost_title(product)
            
            # Генерируем описание
            site_url = request.build_absolute_uri(product.get_absolute_url())
            description = generate_farpost_description(product, site_url)
            
            # Получаем изображения
            photo_urls = generate_farpost_images(product, request)
            # Дополняем до 5 фото
            while len(photo_urls) < 5:
                photo_urls.append('')
            
            # Формируем характеристики (структурированный формат)
            characteristics = ''
            if product.characteristics:
                char_list = product.get_characteristics_list()
                characteristics = '\n'.join([f'{k}: {v}' for k, v in char_list])
            
            writer.writerow([
                title,  # Автоматически сгенерированный заголовок
                str(product.price),
                description,  # Полное структурированное описание
                product.article or '',
                product.brand or '',
                product.get_condition_display(),
                product.get_availability_display(),
                characteristics,  # Структурированные характеристики
                product.applicability or '',
                product.cross_numbers or '',
                photo_urls[0],  # До 5 фото
                photo_urls[1],
                photo_urls[2],
                photo_urls[3],
                photo_urls[4],
                site_url,  # Уникальная ссылка на карточку товара на сайте
                product.category.name if product.category else '',
            ])
        
        return response
    export_farpost.short_description = 'Экспорт для Farpost'


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    """Админка для категорий."""
    list_display = ['tree_actions', 'indented_title', 'slug', 'product_count', 'is_active', 'order']
    list_display_links = ['indented_title']
    list_editable = ['is_active', 'order']
    list_filter = ['is_active', 'level']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'parent', 'image', 'description')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'seo_text'),
            'classes': ('collapse',)
        }),
        ('Настройки', {
            'fields': ('is_active', 'order')
        }),
    )


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin, FarpostExportMixin, admin.ModelAdmin):
    """Админка для товаров."""
    resource_class = ProductResource
    list_display = [
        'image_preview', 'name', 'external_id', 'article', 'brand', 'category', 
        'price', 'availability', 'is_active', 'created_at'
    ]
    list_display_links = ['name']
    list_filter = ['is_active', 'is_featured', 'condition', 'availability', 'category', 'brand']
    list_editable = ['price', 'availability', 'is_active']
    search_fields = ['name', 'external_id', 'article', 'brand', 'cross_numbers', 'applicability']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [ProductImageInline]
    actions = ['export_farpost', 'make_active', 'make_inactive']
    list_per_page = 50
    save_on_top = True
    
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'external_id', 'article', 'brand', 'category')
        }),
        ('Цена и наличие', {
            'fields': ('price', 'old_price', 'condition', 'availability', 'quantity')
        }),
        ('Описание', {
            'fields': ('short_description', 'description', 'characteristics')
        }),
        ('Применимость', {
            'fields': ('applicability', 'cross_numbers')
        }),
        ('Farpost', {
            'fields': ('farpost_url',),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('properties',),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Настройки', {
            'fields': ('is_active', 'is_featured')
        }),
    )

    def image_preview(self, obj):
        img = obj.get_main_image()
        if img and img.image:
            return format_html('<img src="{}" style="max-height: 50px;"/>', img.image.url)
        return '-'
    image_preview.short_description = 'Фото'

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = 'Сделать активными'

    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
    make_inactive.short_description = 'Сделать неактивными'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Админка для изображений."""
    list_display = ['id', 'product', 'image_preview', 'is_main', 'order']
    list_filter = ['is_main']
    list_editable = ['is_main', 'order']
    search_fields = ['product__name', 'product__article']
    autocomplete_fields = ['product']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px;"/>', obj.image.url)
        return '-'
    image_preview.short_description = 'Превью'


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Админка для брендов."""
    list_display = ['name', 'slug', 'logo_preview', 'is_active', 'order']
    list_editable = ['is_active', 'order']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 30px;"/>', obj.logo.url)
        return '-'
    logo_preview.short_description = 'Логотип'


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    """Админка для логов импорта."""
    list_display = ['filename', 'status', 'total_rows', 'imported_rows', 'error_rows', 'user', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['filename', 'status', 'total_rows', 'imported_rows', 'error_rows', 'errors', 'user', 'created_at']
    date_hierarchy = 'created_at'


@admin.register(OneCExchangeLog)
class OneCExchangeLogAdmin(admin.ModelAdmin):
    """Админка для логов обмена с 1С."""
    list_display = [
        'created_at', 'request_path', 'status', 'status_code', 
        'total_products', 'updated_products', 'created_products', 
        'hidden_products', 'errors_count', 'processing_time', 'request_ip'
    ]
    list_filter = ['status', 'status_code', 'request_format', 'created_at']
    readonly_fields = [
        'request_method', 'request_path', 'request_ip', 'request_headers', 
        'request_body_size', 'request_format', 'status', 'status_code',
        'total_products', 'updated_products', 'created_products', 
        'hidden_products', 'errors_count', 'error_message', 'response_data',
        'processing_time', 'created_at'
    ]
    date_hierarchy = 'created_at'
    search_fields = ['request_path', 'request_ip', 'error_message']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Запрос', {
            'fields': ('request_method', 'request_path', 'request_ip', 'request_format', 'request_body_size', 'request_headers')
        }),
        ('Ответ', {
            'fields': ('status', 'status_code', 'processing_time')
        }),
        ('Статистика', {
            'fields': ('total_products', 'updated_products', 'created_products', 'hidden_products', 'errors_count')
        }),
        ('Детали', {
            'fields': ('error_message', 'response_data'),
            'classes': ('collapse',)
        }),
        ('Время', {
            'fields': ('created_at',)
        }),
    )


# Настройка заголовка админки
admin.site.site_header = 'Управление каталогом'
admin.site.site_title = 'Каталог товаров'
admin.site.index_title = 'Панель управления'

