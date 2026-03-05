from django.contrib import admin
from django.contrib import messages
from django import forms
from django.utils.html import format_html
from django.http import HttpResponse
from mptt.admin import DraggableMPTTAdmin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
import csv
from .models import (
    Category, Product, ProductImage, Brand, ImportLog, OneCExchangeLog, 
    FarpostAPISettings, Promotion, ProductCharacteristic, SyncLog
)


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
            'Ссылка на сайт', 'Категория', 'Производитель'
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
                'Onesimus',
            ])
        
        return response
    export_farpost.short_description = 'Экспорт для Farpost'


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    """Админка для категорий."""
    list_display = ['tree_actions', 'indented_title', 'slug', 'has_keywords', 'product_count', 'is_active', 'order']
    list_display_links = ['indented_title']
    list_editable = ['is_active', 'order']
    list_filter = ['is_active', 'level']
    search_fields = ['name', 'slug', 'keywords']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'parent', 'image', 'description')
        }),
        ('Автоопределение товаров', {
            'fields': ('keywords',),
            'description': 'Укажите ключевые слова через запятую. При импорте товаров система будет автоматически распределять их в эту категорию, если название товара содержит одно из ключевых слов.'
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'seo_text'),
            'classes': ('collapse',)
        }),
        ('Настройки', {
            'fields': ('is_active', 'order')
        }),
    )
    
    def has_keywords(self, obj):
        """Показывает, есть ли у категории ключевые слова."""
        if obj.keywords:
            keywords_list = obj.get_keywords_list()
            if keywords_list:
                return f'✅ {len(keywords_list)} слов'
        return '—'
    has_keywords.short_description = 'Ключевые слова'
    
    def save_model(self, request, obj, form, change):
        """Сохраняем категорию и пересчитываем дерево MPTT при изменении order."""
        old_order = None
        if change and obj.pk:
            try:
                old_obj = Category.objects.get(pk=obj.pk)
                old_order = old_obj.order
            except Category.DoesNotExist:
                pass
        
        super().save_model(request, obj, form, change)
        
        # Если изменился order, пересчитываем дерево MPTT
        if change and old_order is not None and old_order != obj.order:
            Category.objects.rebuild()
    
    def save_formset(self, request, form, formset, change):
        """После сохранения инлайн-форм пересчитываем дерево."""
        super().save_formset(request, form, formset, change)
        # Пересчитываем дерево MPTT после bulk-операций
        Category.objects.rebuild()
    
    def changelist_view(self, request, extra_context=None):
        """При изменении порядка через list_editable пересчитываем дерево."""
        response = super().changelist_view(request, extra_context)
        if request.method == 'POST' and '_save' in request.POST:
            Category.objects.rebuild()
        return response


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin, FarpostExportMixin, admin.ModelAdmin):
    """Админка для товаров."""
    resource_class = ProductResource
    list_display = [
        'image_preview', 'name', 'external_id', 'article', 'brand', 'category', 
        'price', 'wholesale_price', 'availability', 'is_active', 'created_at'
    ]
    list_display_links = ['name']
    list_filter = ['is_active', 'is_featured', 'condition', 'availability', 'category', 'brand']
    list_editable = ['price', 'wholesale_price', 'availability', 'is_active']
    search_fields = ['name', 'external_id', 'article', 'brand', 'cross_numbers', 'applicability']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [ProductImageInline]
    actions = ['export_farpost', 'sync_to_farpost_api', 'make_active', 'make_inactive']
    list_per_page = 50
    save_on_top = True
    
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'external_id', 'article', 'brand', 'category')
        }),
        ('Цена и наличие', {
            'fields': ('price', 'wholesale_price', 'old_price', 'condition', 'availability', 'quantity')
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
    
    def delete_model(self, request, obj):
        """Переопределяем удаление одного товара, чтобы игнорировать ошибки с ProductCharacteristic."""
        from django.db import connection, transaction
        
        try:
            obj.delete()
        except Exception as e:
            # Если ошибка связана с несуществующей таблицей ProductCharacteristic, удаляем через SQL
            error_msg = str(e).lower()
            if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                try:
                    with transaction.atomic():
                        # Удаляем товар напрямую через SQL, минуя CASCADE
                        # Используем ? для SQLite, %s для PostgreSQL
                        with connection.cursor() as cursor:
                            if 'sqlite' in connection.vendor:
                                cursor.execute("DELETE FROM catalog_product WHERE id = ?", [obj.pk])
                            else:
                                cursor.execute("DELETE FROM catalog_product WHERE id = %s", [obj.pk])
                    self.message_user(request, f'Товар "{obj.name}" успешно удалён.', messages.SUCCESS)
                except Exception as sql_error:
                    self.message_user(
                        request,
                        f'Ошибка при удалении товара "{obj.name}": {str(sql_error)}',
                        level=messages.ERROR
                    )
            else:
                # Если это другая ошибка, пробрасываем дальше
                raise
    
    def delete_queryset(self, request, queryset):
        """Переопределяем удаление, чтобы игнорировать ошибки с ProductCharacteristic."""
        from django.db import connection, transaction
        
        deleted_count = 0
        errors_count = 0
        
        for obj in queryset:
            try:
                obj.delete()
                deleted_count += 1
            except Exception as e:
                # Если ошибка связана с несуществующей таблицей ProductCharacteristic, удаляем через SQL
                error_msg = str(e).lower()
                if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                    try:
                        with transaction.atomic():
                            # Удаляем товар напрямую через SQL, минуя CASCADE
                            with connection.cursor() as cursor:
                                if 'sqlite' in connection.vendor:
                                    cursor.execute("DELETE FROM catalog_product WHERE id = ?", [obj.pk])
                                else:
                                    cursor.execute("DELETE FROM catalog_product WHERE id = %s", [obj.pk])
                        deleted_count += 1
                    except Exception:
                        errors_count += 1
                else:
                    # Если это другая ошибка, пробрасываем дальше
                    raise
        
        if deleted_count > 0:
            self.message_user(
                request,
                f'Успешно удалено товаров: {deleted_count}',
                messages.SUCCESS
            )
        if errors_count > 0:
            self.message_user(
                request,
                f'Не удалось удалить товаров: {errors_count}',
                level=messages.WARNING
            )
    
    def sync_to_farpost_api(self, request, queryset):
        """Синхронизировать выбранные товары с API Farpost."""
        from .models import FarpostAPISettings
        from .services import sync_to_farpost_api, generate_farpost_api_file
        
        # Получаем активные настройки API
        api_settings = FarpostAPISettings.objects.filter(is_active=True).first()
        
        if not api_settings:
            self.message_user(
                request,
                'Ошибка: Не настроены учетные данные API Farpost. Перейдите в раздел "Настройки API Farpost" и создайте настройки.',
                level=messages.ERROR
            )
            return
        
        # Проверяем количество товаров и предупреждаем о размере файла
        products_count = queryset.count()
        MAX_FILE_SIZE_MB = 5  # Лимит API Farpost - 5 МБ
        
        # Приблизительная оценка: ~1 КБ на товар (может варьироваться)
        estimated_size_kb = products_count * 1
        estimated_size_mb = estimated_size_kb / 1024
        
        if estimated_size_mb > MAX_FILE_SIZE_MB:
            # Предупреждение о большом размере
            self.message_user(
                request,
                f'⚠️ Предупреждение: Выбрано {products_count} товаров. Примерный размер файла: {estimated_size_mb:.2f} МБ. '
                f'API Farpost принимает файлы до {MAX_FILE_SIZE_MB} МБ. '
                f'Рекомендуется синхронизировать партиями по ~{int(MAX_FILE_SIZE_MB * 1000)} товаров.',
                level=messages.WARNING
            )
            # Можно добавить автоматическое разбиение на части, но пока просто предупреждаем
        
        # Синхронизируем товары
        success, message, response_data = sync_to_farpost_api(
            products=queryset,
            api_settings=api_settings,
            file_format='xls',  # XLS обычно компактнее для больших объемов
            request=request
        )
        
        if success:
            self.message_user(
                request,
                f'✅ {message}. Товаров синхронизировано: {products_count}',
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                f'❌ {message}',
                level=messages.ERROR
            )
            # Если ошибка из-за размера файла, даем подсказку
            if 'размер' in message.lower() or 'size' in message.lower() or 'больш' in message.lower():
                self.message_user(
                    request,
                    '💡 Совет: Разбейте синхронизацию на части. Выберите товары партиями (например, по 3000-4000 товаров за раз).',
                    level=messages.INFO
                )
    sync_to_farpost_api.short_description = 'Синхронизировать с API Farpost'


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
    list_display = ['name', 'slug', 'product_count', 'logo_preview', 'is_active', 'order']
    list_editable = ['is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']
    actions = ['sync_brands_from_products']
    change_list_template = 'admin/catalog/brand_changelist.html'
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'logo', 'description')
        }),
        ('Настройки', {
            'fields': ('is_active', 'order')
        }),
    )

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 30px;"/>', obj.logo.url)
        return '-'
    logo_preview.short_description = 'Логотип'
    
    def product_count(self, obj):
        """Количество товаров с этим брендом."""
        count = Product.objects.filter(brand__iexact=obj.name).count()
        if count > 0:
            url = f"/admin/catalog/product/?brand__iexact={obj.name}"
            return format_html('<a href="{}">{}</a>', url, count)
        return 0
    product_count.short_description = 'Товаров'
    
    @admin.action(description='🔄 Синхронизировать бренды из товаров')
    def sync_brands_from_products(self, request, queryset):
        """Добавляет все бренды из товаров в справочник."""
        from catalog.services import clear_brands_cache
        
        # Получаем уникальные бренды из товаров
        product_brands = Product.objects.exclude(
            brand__isnull=True
        ).exclude(
            brand=''
        ).values_list('brand', flat=True).distinct()
        
        created_count = 0
        existing_count = 0
        
        for brand_name in product_brands:
            brand_name = brand_name.strip()
            if not brand_name:
                continue
            
            # Нормализуем название (первая буква заглавная)
            normalized_name = brand_name.strip()
            
            # Проверяем, есть ли уже такой бренд (без учёта регистра)
            existing = Brand.objects.filter(name__iexact=normalized_name).first()
            if existing:
                existing_count += 1
            else:
                Brand.objects.create(
                    name=normalized_name,
                    is_active=True
                )
                created_count += 1
        
        # Очищаем кэш брендов
        clear_brands_cache()
        
        self.message_user(
            request,
            f'Синхронизация завершена: добавлено {created_count} новых брендов, '
            f'{existing_count} уже существовали.',
            messages.SUCCESS
        )
    
    def save_model(self, request, obj, form, change):
        """Очищает кэш брендов при сохранении."""
        super().save_model(request, obj, form, change)
        from catalog.services import clear_brands_cache
        clear_brands_cache()
    
    def delete_model(self, request, obj):
        """Очищает кэш брендов при удалении."""
        super().delete_model(request, obj)
        from catalog.services import clear_brands_cache
        clear_brands_cache()
    
    def get_urls(self):
        """Добавляет кастомные URL для синхронизации."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('sync-from-products/', self.admin_site.admin_view(self.sync_from_products_view), name='brand_sync_from_products'),
        ]
        return custom_urls + urls
    
    def sync_from_products_view(self, request):
        """View для синхронизации брендов из товаров."""
        from catalog.services import clear_brands_cache
        from django.shortcuts import redirect
        
        # Получаем уникальные бренды из товаров
        product_brands = Product.objects.exclude(
            brand__isnull=True
        ).exclude(
            brand=''
        ).values_list('brand', flat=True).distinct()
        
        # Нормализуем и убираем дубликаты (разный регистр)
        unique_brands = set()
        for brand in product_brands:
            if brand and brand.strip():
                unique_brands.add(brand.strip())
        
        created_count = 0
        
        for brand_name in unique_brands:
            # Проверяем, есть ли уже такой бренд (без учёта регистра)
            if not Brand.objects.filter(name__iexact=brand_name).exists():
                Brand.objects.create(name=brand_name, is_active=True)
                created_count += 1
        
        clear_brands_cache()
        
        total_brands = Brand.objects.count()
        
        if created_count > 0:
            self.message_user(
                request,
                f'Добавлено {created_count} новых брендов. Всего в справочнике: {total_brands}',
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                f'Все бренды уже в справочнике. Всего брендов: {total_brands}',
                messages.INFO
            )
        return redirect('admin:catalog_brand_changelist')
    
    def changelist_view(self, request, extra_context=None):
        """Добавляет кнопки синхронизации на страницу списка."""
        extra_context = extra_context or {}
        extra_context['show_sync_buttons'] = True
        extra_context['sync_from_products_url'] = 'sync-from-products/'
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    """Админка для логов импорта."""
    list_display = ['filename', 'status', 'total_rows', 'imported_rows', 'error_rows', 'user', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['filename', 'status', 'total_rows', 'imported_rows', 'error_rows', 'errors', 'user', 'created_at']
    date_hierarchy = 'created_at'


@admin.register(FarpostAPISettings)
class FarpostAPISettingsAdmin(admin.ModelAdmin):
    """Админка для настроек API Farpost."""
    
    class FarpostAPISettingsForm(forms.ModelForm):
        """Форма для настройки API Farpost с кастомным полем пароля."""
        password_input = forms.CharField(
            label='Пароль',
            required=False,
            widget=forms.PasswordInput(attrs={
                'class': 'vTextField',
            }),
            help_text='Введите пароль для API Farpost (необязательно, если используется ключ API). Оставьте пустым, если не хотите менять существующий пароль.'
        )
        api_key_input = forms.CharField(
            label='Ключ API',
            required=False,
            widget=forms.PasswordInput(attrs={
                'class': 'vTextField',
            }),
            help_text='Ключ для аутентификации в API Farpost (предоставляется Farpost по запросу). '
                      'Используется для расчета auth (SHA512 от ключа). Если указан, имеет приоритет над login:password.'
        )
        
        class Meta:
            model = FarpostAPISettings
            fields = ['login', 'packet_id', 'auto_update_enabled', 'auto_update_url', 'auto_update_interval', 'is_active']
            exclude = ['password', 'api_key']
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Если это редактирование существующего объекта, показываем что ключ уже установлен (но не сам ключ)
            if self.instance and self.instance.pk and self.instance.api_key:
                self.fields['api_key_input'].help_text += ' (Ключ уже установлен. Введите новый ключ, чтобы изменить его.)'
    
    form = FarpostAPISettingsForm
    list_display = ['login', 'packet_id', 'auto_update_enabled', 'is_active', 'last_sync', 'last_sync_status']
    list_filter = ['is_active', 'auto_update_enabled', 'last_sync_status', 'last_sync']
    search_fields = ['login', 'packet_id', 'auto_update_url']
    readonly_fields = ['last_sync', 'last_sync_status', 'last_sync_error', 'last_auto_update', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Учетные данные', {
            'fields': ('login', 'password_input', 'api_key_input', 'packet_id'),
            'description': 'Пакет-объявление на Farpost может содержать множество товаров (тысячи) из разных категорий. '
                          'Один packet_id используется для всех товаров, которые вы хотите синхронизировать. '
                          'Если нужно разделить товары по разным пакетам, создайте несколько настроек с разными packet_id. '
                          '<br><strong>Аутентификация:</strong> Укажите либо ключ API (предпочтительно), либо логин и пароль.'
        }),
        ('Автоматическое обновление', {
            'fields': ('auto_update_enabled', 'auto_update_url', 'auto_update_interval', 'last_auto_update'),
            'description': 'Настройка автоматического периодического обновления прайс-листа по ссылке. '
                          'На странице прайс-листа на Farpost перейдите во вкладку «Автоматически», '
                          'отметьте подходящий способ обновления и вставьте ссылку к вашему прайс-листу.'
        }),
        ('Статус', {
            'fields': ('is_active', 'last_sync', 'last_sync_status', 'last_sync_error')
        }),
        ('Информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Сохраняем модель с обработкой пароля и ключа API."""
        # Получаем пароль из формы
        password_input = form.cleaned_data.get('password_input', '')
        if password_input:
            # Если указан новый пароль, сохраняем его в зашифрованном виде
            obj.set_encrypted_password(password_input)
        
        # Получаем ключ API из формы
        api_key_input = form.cleaned_data.get('api_key_input', '')
        if api_key_input:
            # Сохраняем ключ в зашифрованном виде
            obj.set_encrypted_api_key(api_key_input)
        
        # Проверяем, что указан хотя бы один способ аутентификации
        if not change and not password_input and not api_key_input:
            from django.core.exceptions import ValidationError
            raise ValidationError('Необходимо указать либо ключ API, либо логин и пароль для аутентификации')
        
        # Валидация автоматического обновления
        if obj.auto_update_enabled and not obj.auto_update_url:
            from django.core.exceptions import ValidationError
            raise ValidationError('Для включения автоматического обновления необходимо указать ссылку на прайс-лист')
        
        if obj.auto_update_interval < 1:
            obj.auto_update_interval = 1
        
        super().save_model(request, obj, form, change)


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


# Регистрируем ProductCharacteristic только если таблица существует
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_productcharacteristic'")
        table_exists = cursor.fetchone() is not None
    
    if table_exists:
        @admin.register(ProductCharacteristic)
        class ProductCharacteristicAdmin(admin.ModelAdmin):
            """Админка для характеристик товаров."""
            list_display = ['product', 'name', 'value', 'order', 'created_at']
            list_display_links = ['name']
            list_editable = ['order']
            list_filter = ['created_at', 'product']
            search_fields = ['name', 'value', 'product__name', 'product__article']
            ordering = ['product', 'order', 'name']
            raw_id_fields = ['product']
except Exception:
    # Если таблица не существует, не регистрируем админку
    pass


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    """Админка для логов синхронизации."""
    list_display = ['operation_type', 'status', 'processed_count', 'created_count', 'updated_count', 'errors_count', 'created_at']
    list_display_links = ['created_at']
    list_filter = ['operation_type', 'status', 'created_at', 'request_format']
    search_fields = ['message', 'filename', 'request_ip']
    readonly_fields = [
        'operation_type', 'status', 'message', 'processed_count', 'created_count', 
        'updated_count', 'errors_count', 'errors', 'request_ip', 'request_format', 
        'filename', 'created_at', 'processing_time'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('operation_type', 'status', 'message', 'created_at', 'processing_time')
        }),
        ('Статистика', {
            'fields': ('processed_count', 'created_count', 'updated_count', 'errors_count')
        }),
        ('Детали запроса', {
            'fields': ('request_ip', 'request_format', 'filename')
        }),
        ('Ошибки', {
            'fields': ('errors',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Запрещаем создание логов вручную."""
        return False


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    """Админка для акций и специальных предложений."""
    list_display = ['image_preview', 'title', 'is_active', 'order', 'created_at']
    list_display_links = ['title']
    list_editable = ['is_active', 'order']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'description']
    ordering = ['order', '-created_at']
    
    fieldsets = (
        ('Основное', {
            'fields': ('title', 'image', 'link', 'description')
        }),
        ('Настройки', {
            'fields': ('is_active', 'order')
        }),
    )
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px;"/>', obj.image.url)
        return '-'
    image_preview.short_description = 'Превью'


# Настройка заголовка админки
admin.site.site_header = 'Управление каталогом'
admin.site.site_title = 'Каталог товаров'
admin.site.index_title = 'Панель управления'

