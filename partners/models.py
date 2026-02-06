from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from catalog.models import Product


class PartnerRequest(models.Model):
    """Заявка на партнёрство."""
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрена'),
        ('rejected', 'Отклонена'),
    ]
    
    # Контактные данные
    full_name = models.CharField('ФИО контактного лица', max_length=255)
    phone = models.CharField('Телефон', max_length=50)
    email = models.EmailField('E-mail')
    city = models.CharField('Город', max_length=100)
    comment = models.TextField('Комментарий', blank=True)
    
    # Статус и управление
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_comment = models.TextField('Комментарий администратора', blank=True)
    
    # Связь с партнёром (после одобрения)
    partner = models.OneToOneField(
        'Partner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request',
        verbose_name='Партнёр'
    )
    
    # Служебные поля
    created_at = models.DateTimeField('Дата заявки', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)
    processed_at = models.DateTimeField('Дата обработки', null=True, blank=True)
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_partner_requests',
        verbose_name='Обработал'
    )
    
    class Meta:
        verbose_name = 'Заявка партнёра'
        verbose_name_plural = 'Заявки партнёров'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.full_name} ({self.email}) - {self.get_status_display()}'
    
    def approve(self, admin_user=None):
        """Одобрить заявку и создать партнёра."""
        if self.status == 'approved':
            return None
        
        self.status = 'approved'
        self.processed_at = timezone.now()
        self.processed_by = admin_user
        self.save()
        return self.partner
    
    def reject(self, admin_user=None, comment=''):
        """Отклонить заявку."""
        self.status = 'rejected'
        self.processed_at = timezone.now()
        self.processed_by = admin_user
        if comment:
            self.admin_comment = comment
        self.save()


class Partner(models.Model):
    """Модель партнёра (оптового покупателя)."""
    # Связь с пользователем Django
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='partner_profile',
        verbose_name='Пользователь'
    )
    
    # Контактные данные
    company_name = models.CharField('Название компании', max_length=255, blank=True)
    full_name = models.CharField('ФИО контактного лица', max_length=255)
    phone = models.CharField('Телефон', max_length=50)
    city = models.CharField('Город', max_length=100)
    
    # Дополнительно
    inn = models.CharField('ИНН', max_length=20, blank=True)
    kpp = models.CharField('КПП', max_length=20, blank=True)
    legal_address = models.TextField('Юридический адрес', blank=True)
    
    # Доступ и настройки
    is_active = models.BooleanField('Активен', default=True)
    discount_percent = models.DecimalField(
        'Скидка %', 
        max_digits=5, 
        decimal_places=2, 
        default=0,
        help_text='Индивидуальная скидка партнёра (0-100%)'
    )
    
    # Служебные поля
    created_at = models.DateTimeField('Зарегистрирован', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    last_login = models.DateTimeField('Последний вход', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Партнёр'
        verbose_name_plural = 'Партнёры'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.company_name:
            return f'{self.company_name} ({self.full_name})'
        return self.full_name
    
    @property
    def email(self):
        return self.user.email


class PartnerSettings(models.Model):
    """Настройки раздела для партнёров (синглтон)."""
    # Email для уведомлений о заявках
    manager_email = models.EmailField(
        'Email менеджера по опту',
        help_text='Email для получения уведомлений о новых заявках партнёров'
    )
    
    # Тексты для страницы
    cooperation_conditions = models.TextField(
        'Условия сотрудничества',
        blank=True,
        help_text='HTML разметка разрешена'
    )
    advantages = models.TextField(
        'Преимущества работы с компанией',
        blank=True,
        help_text='HTML разметка разрешена'
    )
    access_procedure = models.TextField(
        'Порядок получения оптового доступа',
        blank=True,
        help_text='HTML разметка разрешена'
    )
    
    # Отображаемые тексты
    price_hidden_text = models.CharField(
        'Текст вместо цены',
        max_length=255,
        default='Цена доступна после регистрации',
        help_text='Текст, который видят незарегистрированные пользователи вместо цены'
    )
    
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        verbose_name = 'Настройки партнёрского раздела'
        verbose_name_plural = 'Настройки партнёрского раздела'
    
    def __str__(self):
        return 'Настройки партнёрского раздела'
    
    def save(self, *args, **kwargs):
        # Гарантируем только одну запись
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Получить или создать настройки."""
        obj, created = cls.objects.get_or_create(pk=1, defaults={
            'manager_email': 'onesimus25@mail.ru'
        })
        return obj


class PartnerOrder(models.Model):
    """Заказ партнёра."""
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('pending', 'Ожидает обработки'),
        ('processing', 'В обработке'),
        ('completed', 'Завершён'),
        ('cancelled', 'Отменён'),
    ]
    
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='Партнёр'
    )
    
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Комментарий партнёра к заказу
    comment = models.TextField('Комментарий партнёра', blank=True, help_text='Комментарий к заказу от партнёра')
    
    # Служебные поля
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    
    class Meta:
        verbose_name = 'Заказ партнёра'
        verbose_name_plural = 'Заказы партнёров'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Заказ #{self.id} от {self.partner.full_name} ({self.created_at.strftime("%d.%m.%Y")})'
    
    def get_total_price(self):
        """Подсчёт общей стоимости заказа."""
        return sum(item.get_total() for item in self.items.all())
    
    def get_total_quantity(self):
        """Подсчёт общего количества товаров."""
        return sum(item.quantity for item in self.items.all())


class PartnerOrderItem(models.Model):
    """Товар в заказе партнёра."""
    order = models.ForeignKey(
        PartnerOrder,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заказ'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name='Товар'
    )
    quantity = models.PositiveIntegerField('Количество', default=1)
    price = models.DecimalField(
        'Цена за единицу',
        max_digits=12,
        decimal_places=2
    )
    
    # Время добавления товара в заказ
    added_at = models.DateTimeField('Добавлен', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Товар в заказе партнёра'
        verbose_name_plural = 'Товары в заказе партнёра'
        ordering = ['added_at']
    
    def __str__(self):
        return f'{self.product.name} x{self.quantity}'
    
    def get_total(self):
        """Подсчёт стоимости товара в заказе."""
        return self.price * self.quantity
