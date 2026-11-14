from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.db import models
from django.forms import Textarea
from .models import HeroCarouselSettings, HeroSlide, Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Админка для редактируемых страниц."""
    list_display = ('get_slug_display', 'title', 'is_active', 'updated_at', 'preview_link')
    list_display_links = ('get_slug_display', 'title')  # Клик по названию открывает редактирование
    list_filter = ('is_active', 'slug')
    # Убираем поиск - не нужен
    # search_fields = ('title', 'content')
    readonly_fields = ('updated_at', 'preview_link')
    list_editable = ('is_active',)  # Можно менять активность прямо в списке
    save_on_top = True  # Кнопки сохранения сверху
    show_full_result_count = False  # Убираем счетчик результатов
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('slug', 'title', 'is_active')
        }),
        ('Содержимое страницы', {
            'fields': ('content',),
            'description': 'Можно использовать HTML разметку. Для форматирования используйте HTML теги: &lt;p&gt;, &lt;h2&gt;, &lt;ul&gt;, &lt;li&gt;, &lt;strong&gt;, &lt;em&gt; и т.д.'
        }),
        ('SEO настройки', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',),
            'description': 'Эти поля используются для поисковых систем. Если не заполнены, используются значения по умолчанию.'
        }),
        ('Превью и информация', {
            'fields': ('preview_link', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 30, 'cols': 100, 'style': 'width: 100%; max-width: 100%; font-family: monospace;'})},
    }
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:  # При редактировании slug нельзя менять
            readonly.append('slug')
        return readonly
    
    def preview_link(self, obj):
        """Ссылка на просмотр страницы на сайте."""
        if obj and obj.pk:
            url = obj.get_absolute_url()
            return format_html(
                '<a href="{}" target="_blank" style="color: #417690; font-weight: bold;">'
                '👁️ Посмотреть на сайте</a>',
                url
            )
        return '-'
    preview_link.short_description = 'Просмотр'
    
    def get_slug_display(self, obj):
        """Отображает читаемое название типа страницы."""
        return obj.get_slug_display() if obj else ''
    get_slug_display.short_description = 'Тип страницы'
    get_slug_display.admin_order_field = 'slug'


@admin.register(HeroCarouselSettings)
class HeroCarouselSettingsAdmin(admin.ModelAdmin):
    """Скорость слайдшоу и сколько изображений выводить на главной."""

    fieldsets = (
        ('Параметры показа', {
            'fields': ('interval_seconds', 'visible_count', 'images_link'),
            'description': (
                'Эти значения применяются к карусели на главной странице. '
                'Сами изображения добавляются в разделе «Изображения карусели»: '
                'их можно загрузить, заменить, удалить и расставить по порядку.'
            ),
        }),
    )
    readonly_fields = ('images_link',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        settings_obj = HeroCarouselSettings.load()
        return redirect(reverse('admin:core_herocarouselsettings_change', args=[settings_obj.pk]))

    def images_link(self, obj):
        url = reverse('admin:core_heroslide_changelist')
        return format_html(
            '<a href="{}" style="font-weight: 600;">Открыть изображения карусели</a>',
            url,
        )
    images_link.short_description = 'Изображения'


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    """Загрузка, замена, удаление и порядок кадров карусели."""

    list_display = ('preview', 'caption', 'is_active', 'order', 'updated_at')
    list_display_links = ('preview', 'caption')
    list_editable = ('is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('alt',)
    ordering = ('order', 'id')
    save_on_top = True
    readonly_fields = ('preview_large', 'created_at', 'updated_at')
    fieldsets = (
        ('Изображение', {
            'fields': ('image', 'preview_large', 'alt'),
            'description': (
                'Загрузите файл, чтобы добавить изображение. '
                'Чтобы заменить его, откройте запись и выберите новый файл — старый будет удалён. '
                'Порядок на главной задаётся числом в поле «Порядок»: меньшее значение показывается раньше.'
            ),
        }),
        ('Показ', {
            'fields': ('is_active', 'order', 'created_at', 'updated_at'),
        }),
    )

    def caption(self, obj):
        return obj.alt or f'Изображение #{obj.pk}'
    caption.short_description = 'Подпись'
    caption.admin_order_field = 'alt'

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" alt="" style="height: 48px; width: 96px; object-fit: contain; background: #111; border-radius: 4px;"/>',
                obj.image.url,
            )
        return '—'
    preview.short_description = 'Превью'

    def preview_large(self, obj):
        if obj and obj.pk and obj.image:
            return format_html(
                '<img src="{}" alt="" style="max-width: 100%; max-height: 240px; object-fit: contain; background: #111; border-radius: 8px;"/>',
                obj.image.url,
            )
        return 'После сохранения здесь появится превью.'
    preview_large.short_description = 'Текущее изображение'

