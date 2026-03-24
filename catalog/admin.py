from django.contrib import admin
from django.contrib import messages
from django import forms
from django.utils.html import format_html
from django.http import HttpResponse
from django.db.models import Q
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
    
    def get_export_queryset(self):
        """Переопределяем, чтобы избежать ошибок с ProductCharacteristic."""
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                if 'sqlite' in connection.vendor:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_productcharacteristic'")
                else:
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name='catalog_productcharacteristic'")
                table_exists = cursor.fetchone() is not None
        except Exception:
            table_exists = False
        
        if not table_exists:
            # Используем безопасный queryset без обращения к product_characteristics
            return Product.objects.all().select_related('category').prefetch_related('images')
        else:
            return super().get_export_queryset()

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
            generate_farpost_images,
            clean_product_name,
            build_farpost_compact_name,
        )
        import io as _io
        
        output = _io.StringIO()
        writer = csv.writer(output, delimiter=';')
        # Заголовки для Farpost
        # ВАЖНО: Первым столбцом должен быть "Наименование" - Фарпост с первого столбца берет наименование товара
        # Удален столбец "Заголовок" - Фарпост не хочет его считывать
        # Столбец "Производитель" возвращен - Фарпост должен получать производителя "Onesimus" из прайс-листа
        writer.writerow([
            'Наименование', 'Цена', 'Артикул', 'Бренд',
            'Состояние', 'Наличие', 'Количество', 'Характеристика',
            'Применимо для моделей', 'Применимо для двигателей',
            'Кросс-номера', 'Фото1', 'Фото2', 'Фото3', 'Фото4', 'Фото5',
            'Ссылка на сайт', 'Категория', 'Производитель'
        ])
        
        no_article_count = 0
        zero_price_count = 0
        for product in queryset:
            site_url = request.build_absolute_uri(product.get_absolute_url())
            photo_urls = generate_farpost_images(product, request)
            while len(photo_urls) < 5:
                photo_urls.append('')
            
            characteristics = ''
            models_value = ''
            engines_value = ''
            export_cross_numbers = (product.cross_numbers or '').strip()
            if product.characteristics:
                char_list = product.get_characteristics_list()
                normalized_lines = []
                seen = set()
                extracted_cross = []
                for k, v in char_list:
                    key_norm = str(k).strip().lower()
                    val_str = str(v).strip()
                    if key_norm in ('кросс-номер', 'кросс номер', 'cross numbers', 'cross_numbers', 'примечание', 'note'):
                        extracted_cross.extend([x.strip() for x in val_str.replace('\n', ',').split(',') if x.strip()])
                        continue
                    if key_norm in ('артикул2', 'article2', 'oem', 'oem номер', 'oem-номер'):
                        continue
                    if key_norm in ('кузов', 'body'):
                        if not models_value:
                            models_value = val_str
                        continue
                    if key_norm in ('двигатель', 'engine'):
                        if not engines_value:
                            engines_value = val_str
                        continue
                    if key_norm in ('размер', 'size', 'характеристика', 'характеристики'):
                        line = f'Характеристика: {val_str}'
                    else:
                        line = f'{k}: {val_str}'
                    if line not in seen:
                        seen.add(line)
                        normalized_lines.append(line)
                characteristics = '\n'.join(normalized_lines)

                if not export_cross_numbers and extracted_cross:
                    uniq = []
                    seen_x = set()
                    for x in extracted_cross:
                        xl = x.lower()
                        if xl not in seen_x:
                            seen_x.add(xl)
                            uniq.append(x)
                    export_cross_numbers = ', '.join(uniq)
            
            quantity = product.quantity if product.is_active else 0
            
            if not product.article:
                no_article_count += 1
            if not product.price or product.price == 0:
                zero_price_count += 1
            
            # ВАЖНО: Используем полное название товара, а не очищенное
            # Фарпост должен видеть полное наименование товара
            full_name = build_farpost_compact_name(product)
            
            writer.writerow([
                full_name,  # Полное наименование товара (первый столбец)
                str(product.price),
                product.article or '',
                product.brand or '',
                product.get_condition_display(),
                product.get_availability_display(),
                quantity,
                characteristics,
                models_value,
                engines_value,
                export_cross_numbers,
                photo_urls[0],
                photo_urls[1],
                photo_urls[2],
                photo_urls[3],
                photo_urls[4],
                site_url,
                product.category.name if product.category else '',
                'Onesimus',  # Производитель по умолчанию
            ])
        
        content = output.getvalue().encode('utf-8-sig')
        response = HttpResponse(content, content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="farpost_export.csv"'
        
        # Предупреждения через message_user (messages импортирован на уровне модуля)
        warn = messages.WARNING
        if no_article_count:
            self.message_user(
                request,
                f'Экспортировано. ВНИМАНИЕ: {no_article_count} товаров без артикула — '
                f'Farpost требует уникальный артикул для каждого товара.',
                level=warn,
            )
        if zero_price_count:
            self.message_user(
                request,
                f'ВНИМАНИЕ: {zero_price_count} товаров с ценой 0 — '
                f'Farpost не принимает объявления с нулевой ценой.',
                level=warn,
            )
        
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

        # Автосоздание/обновление подкатегорий из ключевых слов
        # (актуально, когда пользователь ожидает, что keywords -> список подкатегорий)
        try:
            from catalog.services import sync_subcategories_from_keywords
            sync_subcategories_from_keywords(obj, deactivate_removed=True)
        except Exception:
            # Не ломаем сохранение категории из-за авто-синхронизации
            pass
        
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


class PriceFilter(admin.SimpleListFilter):
    """Фильтр по наличию цены."""
    title = 'Цена'
    parameter_name = 'price_status'

    def lookups(self, request, model_admin):
        return [
            ('with_price', 'С ценой (> 0)'),
            ('no_price', 'Без цены (= 0)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'with_price':
            return queryset.filter(price__gt=0)
        if self.value() == 'no_price':
            return queryset.filter(price=0)
        return queryset


class PriceTypeFilter(admin.SimpleListFilter):
    """Фильтр по типу цены товара."""
    title = 'Тип цены'
    parameter_name = 'price_type'

    def lookups(self, request, model_admin):
        return [
            ('retail', 'Розничная (price > 0)'),
            ('wholesale', 'Оптовая (wholesale_price > 0)'),
            ('both', 'Обе цены'),
            ('none', 'Без цены'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'retail':
            return queryset.filter(price__gt=0)
        if self.value() == 'wholesale':
            return queryset.filter(wholesale_price__gt=0)
        if self.value() == 'both':
            return queryset.filter(price__gt=0, wholesale_price__gt=0)
        if self.value() == 'none':
            return queryset.filter(price=0).filter(Q(wholesale_price__isnull=True) | Q(wholesale_price=0))
        return queryset


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin, FarpostExportMixin, admin.ModelAdmin):
    """Админка для товаров."""
    resource_class = ProductResource
    list_display = [
        'image_preview', 'name', 'external_id', 'article', 'brand', 'category', 
        'price', 'wholesale_price', 'availability', 'is_active', 'created_at'
    ]
    list_display_links = ['name']
    list_filter = [
        'catalog_type', 'is_active', 'is_featured', 'condition', 'availability', 'category', 'brand',
        PriceFilter, PriceTypeFilter
    ]
    list_editable = ['price', 'wholesale_price', 'availability', 'is_active']
    search_fields = ['name', 'external_id', 'article', 'brand', 'cross_numbers', 'applicability']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [ProductImageInline]
    actions = ['export_farpost', 'sync_to_farpost_api', 'make_active', 'make_inactive', 'delete_all_products']
    list_per_page = 100  # Оптимизировано для производительности (было 10000 - слишком много)
    list_max_show_all = 50000  # Максимальное количество товаров, которые можно выбрать сразу (увеличено для массового удаления)
    
    def delete_all_products(self, request, queryset):
        """Удалить ВСЕ товары в базе данных (независимо от выбора)."""
        from django.db import connection, transaction
        from django.shortcuts import redirect
        from django.urls import reverse
        from django.contrib import messages
        
        # Получаем ВСЕ товары, а не только выбранные
        all_products = self.get_queryset(request)
        total_count = all_products.count()
        
        if total_count == 0:
            self.message_user(request, 'Нет товаров для удаления.', messages.WARNING)
            return redirect(reverse('admin:catalog_product_changelist'))
        
        # Проверяем подтверждение
        if request.POST.get('confirm_delete_all') == 'yes':
            table_exists = self._check_table_exists()
            deleted_count = 0
            errors_count = 0
            
            # Используем batch удаление для производительности
            batch_size = 1000
            product_ids = list(all_products.values_list('id', flat=True))
            
            for i in range(0, len(product_ids), batch_size):
                batch_ids = product_ids[i:i + batch_size]
                try:
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            # Удаляем изображения
                            if 'sqlite' in connection.vendor:
                                cursor.execute(
                                    "DELETE FROM catalog_productimage WHERE product_id IN ({})".format(
                                        ','.join(['?' for _ in batch_ids])
                                    ),
                                    batch_ids
                                )
                                cursor.execute(
                                    "DELETE FROM catalog_product WHERE id IN ({})".format(
                                        ','.join(['?' for _ in batch_ids])
                                    ),
                                    batch_ids
                                )
                            else:
                                cursor.execute(
                                    "DELETE FROM catalog_productimage WHERE product_id IN ({})".format(
                                        ','.join(['%s' for _ in batch_ids])
                                    ),
                                    batch_ids
                                )
                                cursor.execute(
                                    "DELETE FROM catalog_product WHERE id IN ({})".format(
                                        ','.join(['%s' for _ in batch_ids])
                                    ),
                                    batch_ids
                                )
                    deleted_count += len(batch_ids)
                except Exception as e:
                    errors_count += len(batch_ids)
                    self.message_user(
                        request,
                        f'Ошибка при удалении партии товаров: {str(e)}',
                        level=messages.ERROR
                    )
            
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
            
            return redirect(reverse('admin:catalog_product_changelist'))
        
        # Показываем страницу подтверждения
        from django.template.response import TemplateResponse
        context = {
            'title': 'Подтверждение удаления всех товаров',
            'objects_name': 'товаров',
            'total_count': total_count,
            'queryset': all_products[:10],  # Показываем первые 10 для примера
            'action_checkbox_name': 'delete_all',
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
        }
        return TemplateResponse(
            request,
            'admin/catalog/product_delete_all_confirmation.html',
            context
        )
    
    delete_all_products.short_description = 'Удалить ВСЕ товары'
    save_on_top = True
    
    def get_actions(self, request):
        """Переопределяем actions, чтобы использовать наш delete_selected вместо стандартного."""
        actions = super().get_actions(request)
        # Удаляем стандартное delete_selected и добавляем наш
        if 'delete_selected' in actions:
            del actions['delete_selected']
        # Добавляем наш метод как действие
        actions['delete_selected'] = (
            self.delete_selected,
            'delete_selected',
            'Удалить выбранные товары'
        )
        return actions
    
    def get_queryset(self, request):
        """Переопределяем queryset для оптимизации производительности."""
        qs = super().get_queryset(request)
        # ВАЖНО: Оптимизируем запросы для производительности
        # Используем только необходимые select_related и prefetch_related
        # Не загружаем images для списка (только при необходимости)
        qs = qs.select_related('category')
        # Избегаем prefetch_related('images') для списка - это замедляет загрузку
        # Images будут загружены только при просмотре конкретного товара
        return qs
    
    def _check_table_exists(self):
        """Проверяет существование таблицы catalog_productcharacteristic."""
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                if 'sqlite' in connection.vendor:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_productcharacteristic'")
                else:
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name='catalog_productcharacteristic'")
                return cursor.fetchone() is not None
        except Exception:
            return False
    
    def get_deleted_objects(self, objs, request):
        """Переопределяем, чтобы ВСЕГДА возвращать правильный формат model_count."""
        # НИКОГДА не вызываем super() - всегда создаём model_count вручную
        # Это гарантирует, что model_count всегда будет словарём
        model_count = {}
        nested = []
        perms_needed = set()
        
        for obj in objs:
            model = obj.__class__
            model_key = f"{model._meta.app_label}.{model._meta.model_name}"
            if model_key not in model_count:
                model_count[model_key] = 0
            model_count[model_key] += 1
            
            # Добавляем товар в nested список
            nested.append([str(obj)])
        
        # model_count ВСЕГДА словарь с ключами вида "app.model"
        return nested, model_count, perms_needed
    
    def response_action(self, request, queryset):
        """Переопределяем, чтобы обработать ошибки с ProductCharacteristic при действиях."""
        action = request.POST.get('action')
        
        # ВАЖНО: Проверяем select_across - если выбраны все товары, получаем полный queryset
        # Django admin передает select_across как строку "1" или "0"
        select_across = request.POST.get('select_across', '0')
        if select_across == '1' or select_across is True:
            # Пользователь выбрал "Выбрать все" - получаем ВСЕ товары из базы
            # ВАЖНО: Игнорируем queryset, так как он содержит только товары с текущей страницы
            queryset = self.get_queryset(request)
            # Логируем для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'DEBUG response_action: select_across={select_across}, queryset.count()={queryset.count()}')
        
        # Если действие - удаление, ВСЕГДА обрабатываем через наш метод, не вызывая super()
        # Это гарантирует, что мы не обратимся к несуществующей таблице
        if action == 'delete_selected':
            # Вызываем наш метод напрямую, минуя стандартный обработчик
            return self.delete_selected(request, queryset)
        
        # Для других случаев используем стандартный метод
        try:
            return super().response_action(request, queryset)
        except Exception as e:
            error_msg = str(e).lower()
            if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                # Если ошибка связана с ProductCharacteristic, обрабатываем вручную
                if action == 'delete_selected':
                    return self.delete_selected(request, queryset)
                else:
                    raise
            else:
                raise
    
    def changelist_view(self, request, extra_context=None):
        """Переопределяем changelist_view, чтобы обработать ошибки с ProductCharacteristic."""
        # ВСЕГДА перехватываем delete_selected до вызова super(), чтобы избежать ошибки
        if request.method == 'POST' and request.POST.get('action') == 'delete_selected':
            # Перехватываем удаление до вызова super(), чтобы избежать ошибки
            # Получаем queryset из POST данных
            from django.contrib.admin import helpers
            selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            
            # ВАЖНО: Проверяем select_across - Django admin передает его как строку "1" или "0"
            select_across_str = request.POST.get('select_across', '0')
            select_across = select_across_str == '1' or select_across_str is True
            
            # Логируем для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'DEBUG changelist_view: select_across={select_across_str}, selected.count()={len(selected)}')
            
            # Если выбраны все товары, получаем полный queryset
            # ВАЖНО: При select_across=1 Django admin может передавать selected с товарами только с текущей страницы
            # Поэтому мы ИГНОРИРУЕМ selected и получаем ВСЕ товары
            if select_across:
                # Пользователь выбрал "Выбрать все" - получаем ВСЕ товары из базы
                queryset = self.get_queryset(request)
                logger.info(f'DEBUG changelist_view: select_across=1, получаем ВСЕ товары. Всего: {queryset.count()}')
            elif selected:
                # Выбраны конкретные товары
                queryset = self.get_queryset(request).filter(pk__in=selected)
            else:
                # Если использован компактный формат (для большого количества товаров)
                selected_ids_compact = request.POST.get('selected_ids_compact', '')
                if selected_ids_compact:
                    selected = [id.strip() for id in selected_ids_compact.split(',') if id.strip()]
                    queryset = self.get_queryset(request).filter(pk__in=selected)
                else:
                    # Если selected пустой, возвращаемся на страницу списка с сообщением
                    from django.shortcuts import redirect
                    from django.urls import reverse
                    self.message_user(request, 'Не выбрано ни одного товара для удаления.', messages.WARNING)
                    return redirect(reverse('admin:catalog_product_changelist'))
            
            if queryset:
                # Проверяем, это подтверждение удаления или первый запрос
                # Для обоих случаев (первый запрос и подтверждение) вызываем delete_selected
                return self.delete_selected(request, queryset)
            else:
                # Если queryset пустой, возвращаемся на страницу списка с сообщением
                from django.shortcuts import redirect
                from django.urls import reverse
                self.message_user(request, 'Не выбрано ни одного товара для удаления.', messages.WARNING)
                return redirect(reverse('admin:catalog_product_changelist'))
        
        # Обертываем весь остальной код в try-except для перехвата любых ошибок
        try:
            # Проверяем существование таблицы перед вызовом super()
            table_exists = self._check_table_exists()
            
            # Если таблицы нет, используем базовый ModelAdmin.changelist_view вместо ImportExportModelAdmin
            if not table_exists:
                # Временно заменяем get_queryset на безопасную версию
                original_get_queryset = self.get_queryset
                def safe_get_queryset(request):
                    return Product.objects.all().select_related('category').prefetch_related('images')
                self.get_queryset = safe_get_queryset
                
                try:
                    # Используем changelist_view из базового ModelAdmin, минуя ImportExportModelAdmin
                    # Это обходит проблему с автоматическим экспортом связанных моделей
                    return admin.ModelAdmin.changelist_view(self, request, extra_context)
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                        # Если ошибка все еще возникла, возможно это действие delete_selected
                        # Попробуем обработать его напрямую
                        if request.method == 'POST' and request.POST.get('action') == 'delete_selected':
                            from django.contrib.admin import helpers
                            selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
                            if selected:
                                queryset = Product.objects.filter(pk__in=selected)
                                return self.delete_selected(request, queryset)
                        # Иначе используем минимальный queryset
                        def minimal_get_queryset(request):
                            return Product.objects.all()
                        self.get_queryset = minimal_get_queryset
                        try:
                            return admin.ModelAdmin.changelist_view(self, request, extra_context)
                        except Exception:
                            raise
                    else:
                        raise
                finally:
                    # Восстанавливаем оригинальный get_queryset
                    self.get_queryset = original_get_queryset
            else:
                # Если таблица существует, используем обычный путь, но с обработкой ошибок
                try:
                    return super().changelist_view(request, extra_context)
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                        # Если ошибка возникла, возможно это действие delete_selected
                        # Попробуем обработать его напрямую
                        if request.method == 'POST' and request.POST.get('action') == 'delete_selected':
                            from django.contrib.admin import helpers
                            selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
                            if selected:
                                queryset = Product.objects.filter(pk__in=selected)
                                return self.delete_selected(request, queryset)
                            else:
                                from django.shortcuts import redirect
                                from django.urls import reverse
                                self.message_user(request, 'Не выбрано ни одного товара для удаления.', messages.WARNING)
                                return redirect(reverse('admin:catalog_product_changelist'))
                        # Иначе используем базовый ModelAdmin.changelist_view
                        original_get_queryset = self.get_queryset
                        def safe_get_queryset(request):
                            return Product.objects.all().select_related('category').prefetch_related('images')
                        self.get_queryset = safe_get_queryset
                        try:
                            return admin.ModelAdmin.changelist_view(self, request, extra_context)
                        finally:
                            self.get_queryset = original_get_queryset
                    else:
                        raise
        except ValueError as e:
            # Перехватываем ValueError с model_count (Need 2 values to unpack)
            if 'need 2 values to unpack' in str(e).lower() or 'model_count' in str(e).lower():
                # Если это действие delete_selected, обрабатываем его напрямую
                if request.method == 'POST' and request.POST.get('action') == 'delete_selected':
                    from django.contrib.admin import helpers
                    selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
                    if selected:
                        queryset = Product.objects.filter(pk__in=selected)
                        return self.delete_selected(request, queryset)
                    else:
                        from django.shortcuts import redirect
                        from django.urls import reverse
                        self.message_user(request, 'Не выбрано ни одного товара для удаления.', messages.WARNING)
                        return redirect(reverse('admin:catalog_product_changelist'))
            raise
        except Exception as e:
            # Перехватываем любые ошибки, связанные с ProductCharacteristic
            error_msg = str(e).lower()
            if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                # Если это действие delete_selected, обрабатываем его напрямую
                if request.method == 'POST' and request.POST.get('action') == 'delete_selected':
                    from django.contrib.admin import helpers
                    selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
                    if selected:
                        queryset = Product.objects.filter(pk__in=selected)
                        return self.delete_selected(request, queryset)
                    else:
                        from django.shortcuts import redirect
                        from django.urls import reverse
                        self.message_user(request, 'Не выбрано ни одного товара для удаления.', messages.WARNING)
                        return redirect(reverse('admin:catalog_product_changelist'))
            # Иначе пробрасываем ошибку дальше
            raise
    
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
    
    def get_fieldsets(self, request, obj=None):
        """Убираем поле 'Применимость' для оптовых товаров."""
        fieldsets = list(super().get_fieldsets(request, obj))
        
        # Если это оптовый товар, убираем секцию "Применимость"
        if obj and obj.catalog_type == 'wholesale':
            fieldsets = [fs for fs in fieldsets if fs[0] != 'Применимость']
        
        return fieldsets
    
    def get_exclude(self, request, obj=None):
        """Исключаем поле 'applicability' для оптовых товаров."""
        exclude = list(super().get_exclude(request, obj) or [])
        
        # Если это оптовый товар, исключаем поле applicability
        if obj and obj.catalog_type == 'wholesale':
            if 'applicability' not in exclude:
                exclude.append('applicability')
        
        return exclude if exclude else None

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
    
    def delete_selected(self, request, queryset):
        """Простое удаление товаров без использования стандартных шаблонов Django Admin."""
        from django.db import connection, transaction
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # Проверяем существование таблицы ProductCharacteristic
        table_exists = self._check_table_exists()
        
        # ВАЖНО: Проверяем select_across ДО подтверждения - если выбраны все, получаем полный queryset
        # Django admin передает select_across как строку "1" или "0"
        select_across_str = request.POST.get('select_across', '0') or request.GET.get('select_across', '0')
        select_across = select_across_str == '1' or select_across_str is True
        if select_across:
            # Пользователь выбрал "Выбрать все" - получаем ВСЕ товары из базы
            # ВАЖНО: Игнорируем переданный queryset, так как он содержит только товары с текущей страницы
            queryset = self.get_queryset(request)
            # Логируем для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'DEBUG delete_selected: select_across={select_across_str}, queryset.count()={queryset.count()}')
        
        # Если это подтверждение удаления - удаляем сразу
        if request.POST.get('post') == 'yes':
            # ВАЖНО: При подтверждении проверяем select_across снова
            # Это критически важно - если select_across=1, игнорируем selected_ids и удаляем ВСЕ
            select_across_confirm_str = request.POST.get('select_across', '0')
            select_across_confirm = select_across_confirm_str == '1' or select_across_confirm_str is True
            
            if select_across_confirm:
                # Пользователь выбрал "Выбрать все" - используем полный queryset ВСЕХ товаров
                # ВАЖНО: Игнорируем selected_ids, так как они содержат только товары с текущей страницы
                full_queryset = self.get_queryset(request)
                # Логируем для отладки
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f'DEBUG delete_selected confirm: select_across={select_across_confirm_str}, удаляем ВСЕ товары. Всего: {full_queryset.count()}')
            else:
                # Получаем выбранные элементы из POST
                from django.contrib.admin import helpers
                selected_ids = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
                
                if selected_ids:
                    # Если использован компактный формат (для большого количества товаров)
                    if len(selected_ids) == 1 and ',' in selected_ids[0]:
                        # Компактный формат - один элемент со списком ID через запятую
                        selected_ids = [id.strip() for id in selected_ids[0].split(',') if id.strip()]
                    
                    # Получаем полный queryset всех выбранных товаров
                    full_queryset = self.get_queryset(request).filter(pk__in=selected_ids)
                else:
                    # Проверяем компактный формат
                    selected_ids_compact = request.POST.get('selected_ids_compact', '')
                    if selected_ids_compact:
                        selected_ids = [id.strip() for id in selected_ids_compact.split(',') if id.strip()]
                        full_queryset = self.get_queryset(request).filter(pk__in=selected_ids)
                    else:
                        # Если в POST нет выбранных элементов, используем переданный queryset
                        full_queryset = queryset
            
            deleted_count = 0
            errors_count = 0
            
            # Используем iterator() для эффективной обработки больших queryset
            for obj in full_queryset.iterator():
                try:
                    # Если таблицы ProductCharacteristic нет, удаляем напрямую через SQL
                    if not table_exists:
                        with transaction.atomic():
                            with connection.cursor() as cursor:
                                # Сначала удаляем связанные изображения
                                if 'sqlite' in connection.vendor:
                                    cursor.execute("DELETE FROM catalog_productimage WHERE product_id = ?", [obj.pk])
                                    cursor.execute("DELETE FROM catalog_product WHERE id = ?", [obj.pk])
                                else:
                                    cursor.execute("DELETE FROM catalog_productimage WHERE product_id = %s", [obj.pk])
                                    cursor.execute("DELETE FROM catalog_product WHERE id = %s", [obj.pk])
                        deleted_count += 1
                    else:
                        # Пробуем стандартное удаление
                        obj.delete()
                        deleted_count += 1
                except Exception as e:
                    # Если ошибка - удаляем через SQL
                    error_msg = str(e).lower()
                    if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                        try:
                            with transaction.atomic():
                                with connection.cursor() as cursor:
                                    # Сначала удаляем связанные изображения
                                    if 'sqlite' in connection.vendor:
                                        cursor.execute("DELETE FROM catalog_productimage WHERE product_id = ?", [obj.pk])
                                        cursor.execute("DELETE FROM catalog_product WHERE id = ?", [obj.pk])
                                    else:
                                        cursor.execute("DELETE FROM catalog_productimage WHERE product_id = %s", [obj.pk])
                                        cursor.execute("DELETE FROM catalog_product WHERE id = %s", [obj.pk])
                            deleted_count += 1
                        except Exception as sql_error:
                            errors_count += 1
                            self.message_user(
                                request,
                                f'Ошибка при удалении товара "{obj.name}": {str(sql_error)}',
                                level=messages.ERROR
                            )
                    else:
                        errors_count += 1
                        self.message_user(
                            request,
                            f'Ошибка при удалении товара "{obj.name}": {str(e)}',
                            level=messages.ERROR
                        )
            
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
            
            return redirect(reverse('admin:catalog_product_changelist'))
        
        # Показываем простую страницу подтверждения БЕЗ использования model_count
        from django.template.response import TemplateResponse
        from django.contrib.admin.helpers import ActionForm
        from django.contrib.admin import helpers
        from django.utils.translation import gettext as _
        
        opts = self.model._meta
        site_context = self.admin_site.each_context(request)
        
        # ВАЖНО: Проверяем select_across - если выбраны все товары, получаем полный queryset
        # Django admin передает select_across как строку "1" или "0"
        select_across_str = request.POST.get('select_across', '0')
        select_across = select_across_str == '1' or select_across_str is True
        
        # Логируем для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'DEBUG delete_selected (confirmation page): select_across={select_across_str}, queryset.count()={queryset.count()}')
        
        if select_across:
            # Пользователь выбрал "Выбрать все" - получаем ВСЕ товары
            # ВАЖНО: Игнорируем переданный queryset, так как он содержит только товары с текущей страницы
            full_queryset = self.get_queryset(request)
            selected_ids = []  # Не передаем ID, так как удаляем все
            total_count = full_queryset.count()
            logger.info(f'DEBUG delete_selected (confirmation page): select_across=1, получаем ВСЕ товары. Всего: {total_count}')
        else:
            # Получаем выбранные ID из POST
            selected_ids = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            
            # Если использован компактный формат (для большого количества товаров)
            if not selected_ids:
                selected_ids_compact = request.POST.get('selected_ids_compact', '')
                if selected_ids_compact:
                    selected_ids = [id.strip() for id in selected_ids_compact.split(',') if id.strip()]
            
            if not selected_ids:
                # Если в POST нет, пытаемся получить из queryset
                if queryset.exists():
                    selected_ids = list(queryset.values_list('pk', flat=True))
                else:
                    selected_ids = []
            
            # Получаем полный queryset всех выбранных товаров для отображения
            if selected_ids:
                full_queryset = self.get_queryset(request).filter(pk__in=selected_ids)
            else:
                full_queryset = queryset
            total_count = len(selected_ids) if selected_ids else full_queryset.count()
        
        # Создаём простой контекст БЕЗ model_count
        context = {
            **site_context,
            'title': _('Вы уверены?'),
            'objects_name': str(opts.verbose_name_plural),
            'queryset': full_queryset,
            'objects': list(full_queryset[:100]),  # Показываем только первые 100 для отображения
            'selected_ids': selected_ids,  # Передаем все ID для скрытых полей
            'total_count': total_count,  # Общее количество выбранных
            'select_across': select_across,  # Передаем флаг "выбрать все"
            'opts': opts,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'media': self.media,
            'action_form': ActionForm(auto_id=None),
            'form_url': '',
        }
        
        # Используем наш простой шаблон без model_count
        return TemplateResponse(
            request,
            'admin/catalog/product_delete_confirmation.html',
            context
        )
    
    def delete_model(self, request, obj):
        """Переопределяем удаление одного товара, чтобы игнорировать ошибки с ProductCharacteristic."""
        from django.db import connection, transaction
        
        # Проверяем существование таблицы ProductCharacteristic
        table_exists = self._check_table_exists()
        
        try:
            # Если таблицы нет, удаляем напрямую через SQL
            if not table_exists:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        # Сначала удаляем связанные изображения
                        if 'sqlite' in connection.vendor:
                            cursor.execute("DELETE FROM catalog_productimage WHERE product_id = ?", [obj.pk])
                            cursor.execute("DELETE FROM catalog_product WHERE id = ?", [obj.pk])
                        else:
                            cursor.execute("DELETE FROM catalog_productimage WHERE product_id = %s", [obj.pk])
                            cursor.execute("DELETE FROM catalog_product WHERE id = %s", [obj.pk])
                self.message_user(request, f'Товар "{obj.name}" успешно удалён.', messages.SUCCESS)
            else:
                obj.delete()
                self.message_user(request, f'Товар "{obj.name}" успешно удалён.', messages.SUCCESS)
        except Exception as e:
            # Если ошибка связана с несуществующей таблицей ProductCharacteristic, удаляем через SQL
            error_msg = str(e).lower()
            if 'productcharacteristic' in error_msg or 'no such table' in error_msg:
                try:
                    with transaction.atomic():
                        # Удаляем товар напрямую через SQL, минуя CASCADE
                        with connection.cursor() as cursor:
                            # Сначала удаляем связанные изображения
                            if 'sqlite' in connection.vendor:
                                cursor.execute("DELETE FROM catalog_productimage WHERE product_id = ?", [obj.pk])
                                cursor.execute("DELETE FROM catalog_product WHERE id = ?", [obj.pk])
                            else:
                                cursor.execute("DELETE FROM catalog_productimage WHERE product_id = %s", [obj.pk])
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
        
        # Проверяем наличие артикулов (Farpost требует уникальный артикул для каждого товара)
        no_article_count = queryset.filter(article='').count() + queryset.filter(article__isnull=True).count()
        if no_article_count:
            self.message_user(
                request,
                f'⚠️ {no_article_count} из выбранных товаров не имеют артикула. '
                f'Farpost требует уникальный буквенно-цифровой артикул для каждого товара. '
                f'Товары без артикула могут не обновиться корректно на Farpost.',
                level=messages.WARNING
            )
        
        # Проверяем нулевые цены
        from decimal import Decimal
        zero_price_sync_count = queryset.filter(price=0).count()
        if zero_price_sync_count:
            self.message_user(
                request,
                f'⚠️ {zero_price_sync_count} из выбранных товаров имеют цену 0. '
                f'Farpost не принимает объявления с нулевой ценой — заполните поле "Цена".',
                level=messages.WARNING
            )
        
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
            # packet_id необязательный
            if 'packet_id' in self.fields:
                self.fields['packet_id'].required = False
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

