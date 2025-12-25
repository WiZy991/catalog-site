from django.contrib import admin
from django.utils.html import format_html
from django.db import models
from django.forms import Textarea
from .models import Page


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
        models.TextField: {'widget': Textarea(attrs={'rows': 20, 'cols': 100, 'style': 'width: 100%; max-width: 800px;'})},
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

