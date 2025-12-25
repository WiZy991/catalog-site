from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Инлайн для товаров в заказе."""
    model = OrderItem
    readonly_fields = ['product', 'quantity', 'price', 'get_total']
    extra = 0
    
    def get_total(self, obj):
        return f'{obj.get_total()} руб.'
    get_total.short_description = 'Сумма'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Админка для заказов."""
    list_display = ['id', 'customer_name', 'customer_phone', 'status', 'total_price', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['customer_name', 'customer_phone', 'customer_email']
    readonly_fields = ['created_at', 'updated_at', 'total_price']
    inlines = [OrderItemInline]
    list_editable = ['status']
    
    fieldsets = (
        ('Данные клиента', {
            'fields': ('customer_name', 'customer_phone', 'customer_email', 'customer_comment')
        }),
        ('Информация о заказе', {
            'fields': ('status', 'total_price', 'created_at', 'updated_at')
        }),
    )

