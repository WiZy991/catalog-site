from django.db import models
from django.conf import settings
from catalog.models import Product


class Order(models.Model):
    """Заказ."""
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('processing', 'В обработке'),
        ('completed', 'Завершён'),
        ('cancelled', 'Отменён'),
    ]
    
    # Данные клиента
    customer_name = models.CharField('ФИО', max_length=200)
    customer_phone = models.CharField('Телефон', max_length=20)
    customer_email = models.EmailField('Email', blank=True)
    customer_comment = models.TextField('Комментарий', blank=True)
    
    # Статус
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Служебные поля
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    total_price = models.DecimalField('Итоговая сумма', max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Заказ #{self.id} от {self.customer_name}'
    
    def get_total_price(self):
        """Подсчёт общей стоимости заказа."""
        return sum(item.get_total() for item in self.items.all())


class OrderItem(models.Model):
    """Товар в заказе."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    quantity = models.PositiveIntegerField('Количество', default=1)
    price = models.DecimalField('Цена за единицу', max_digits=12, decimal_places=2)
    
    class Meta:
        verbose_name = 'Товар в заказе'
        verbose_name_plural = 'Товары в заказе'
    
    def __str__(self):
        return f'{self.product.name} x{self.quantity}'
    
    def get_total(self):
        """Подсчёт стоимости товара в заказе."""
        return self.price * self.quantity

