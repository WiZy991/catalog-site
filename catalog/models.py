from django.db import models
from django.urls import reverse
from mptt.models import MPTTModel, TreeForeignKey
from django.utils.text import slugify
from transliterate import translit, detect_language
import os


def transliterate_slug(text):
    """Транслитерация русского текста в slug."""
    try:
        if detect_language(text):
            text = translit(text, reversed=True)
    except:
        pass
    return slugify(text, allow_unicode=False)


def category_image_path(instance, filename):
    """Генерация пути для изображений категории."""
    # Используем slug категории вместо оригинального имени файла
    # Это предотвращает проблемы с кириллицей и двойным URL-кодированием
    ext = filename.split('.')[-1] if '.' in filename else 'jpg'
    # Используем slug, если он есть, иначе pk или временное имя
    if instance.slug:
        filename = f'{instance.slug}.{ext}'
    elif instance.pk:
        filename = f'category_{instance.pk}.{ext}'
    else:
        # Для новых категорий используем временное имя на основе name
        slug = transliterate_slug(instance.name)
        filename = f'{slug}.{ext}'
    return os.path.join('categories', filename)


class Category(MPTTModel):
    """Категория товаров с поддержкой неограниченной вложенности."""
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('URL', max_length=200, unique=True, blank=True)
    parent = TreeForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='children',
        verbose_name='Родительская категория'
    )
    image = models.ImageField('Изображение', upload_to=category_image_path, blank=True, null=True)
    description = models.TextField('Описание', blank=True)
    meta_title = models.CharField('Meta Title', max_length=200, blank=True)
    meta_description = models.TextField('Meta Description', blank=True)
    seo_text = models.TextField('SEO текст', blank=True)
    is_active = models.BooleanField('Активна', default=True)
    order = models.PositiveIntegerField('Порядок сортировки', default=0)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['order', 'name']

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = transliterate_slug(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        ancestors = self.get_ancestors(include_self=True)
        path = '/'.join([cat.slug for cat in ancestors])
        return reverse('catalog:category', kwargs={'path': path})

    def get_meta_title(self):
        return self.meta_title or f'{self.name} - купить в каталоге'

    def get_meta_description(self):
        return self.meta_description or f'Каталог {self.name.lower()}. Большой выбор, доступные цены.'

    @property
    def product_count(self):
        """Количество товаров в категории и её подкатегориях."""
        descendants = self.get_descendants(include_self=True)
        return Product.objects.filter(category__in=descendants, is_active=True).count()


class Product(models.Model):
    """Модель товара."""
    
    CONDITION_CHOICES = [
        ('new', 'Новый'),
        ('used', 'Б/У'),
    ]
    
    AVAILABILITY_CHOICES = [
        ('in_stock', 'В наличии'),
        ('order', 'Под заказ'),
        ('out_of_stock', 'Нет в наличии'),
    ]

    # Основные поля
    name = models.CharField('Название', max_length=500)
    slug = models.SlugField('URL', max_length=500, unique=True, blank=True)
    external_id = models.CharField('ID из 1С', max_length=255, unique=True, blank=True, null=True, db_index=True, help_text='Уникальный идентификатор товара из 1С')
    article = models.CharField('Кросс-номер', max_length=100, blank=True, db_index=True)
    brand = models.CharField('Бренд', max_length=200, blank=True, db_index=True)
    
    # Категория
    category = TreeForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products',
        verbose_name='Категория'
    )
    
    # Цена и наличие
    price = models.DecimalField('Цена', max_digits=12, decimal_places=2, default=0)
    old_price = models.DecimalField('Старая цена', max_digits=12, decimal_places=2, null=True, blank=True)
    condition = models.CharField('Состояние', max_length=20, choices=CONDITION_CHOICES, default='new')
    availability = models.CharField('Наличие', max_length=20, choices=AVAILABILITY_CHOICES, default='in_stock')
    quantity = models.PositiveIntegerField('Количество', default=0)
    
    # Описание и характеристики
    short_description = models.TextField('Краткое описание', blank=True)
    description = models.TextField('Полное описание', blank=True)
    characteristics = models.TextField('Характеристики', blank=True, help_text='Формат: ключ: значение (каждая с новой строки)')
    
    # Применимость и кросс-номера
    applicability = models.TextField('Применимость', blank=True, help_text='Марки и модели техники')
    cross_numbers = models.TextField('Кросс-номера', blank=True, help_text='Аналоги и взаимозаменяемые номера')
    
    # Farpost интеграция
    farpost_url = models.URLField('Ссылка на Farpost', blank=True)
    
    # Дополнительные свойства (JSON)
    properties = models.JSONField('Дополнительные свойства', default=dict, blank=True, help_text='JSON объект с дополнительными свойствами товара')
    
    # SEO
    meta_title = models.CharField('Meta Title', max_length=200, blank=True)
    meta_description = models.TextField('Meta Description', blank=True)
    
    # Служебные поля
    is_active = models.BooleanField('Активен', default=True)
    is_featured = models.BooleanField('Рекомендуемый', default=False)
    views_count = models.PositiveIntegerField('Просмотры', default=0)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['article']),
            models.Index(fields=['brand']),
            models.Index(fields=['price']),
            models.Index(fields=['is_active', 'availability']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = transliterate_slug(f'{self.name}-{self.article}' if self.article else self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.category:
            ancestors = self.category.get_ancestors(include_self=True)
            path = '/'.join([cat.slug for cat in ancestors])
            return reverse('catalog:product', kwargs={'category_path': path, 'slug': self.slug})
        return reverse('catalog:product_simple', kwargs={'slug': self.slug})

    def get_main_image(self):
        """Получить главное изображение товара."""
        main = self.images.filter(is_main=True).first()
        if main:
            return main
        return self.images.first()

    def get_meta_title(self):
        if self.meta_title:
            return self.meta_title
        parts = [self.name]
        if self.brand:
            parts.append(self.brand)
        if self.article:
            parts.append(self.article)
        return ' | '.join(parts)

    def get_meta_description(self):
        if self.meta_description:
            return self.meta_description
        parts = [f'{self.name}']
        if self.brand:
            parts.append(f'Бренд: {self.brand}')
        if self.article:
            parts.append(f'Кросс-номер: {self.article}')
        if self.price:
            parts.append(f'Цена: {self.price} руб.')
        return '. '.join(parts)

    def get_characteristics_list(self):
        """Преобразует характеристики в список кортежей (ключ, значение)."""
        if not self.characteristics:
            return []
        result = []
        for line in self.characteristics.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                result.append((key.strip(), value.strip()))
        return result

    def get_cross_numbers_list(self):
        """Преобразует кросс-номера в список."""
        if not self.cross_numbers:
            return []
        return [n.strip() for n in self.cross_numbers.split(',') if n.strip()]

    def get_applicability_list(self):
        """Преобразует применимость в список."""
        if not self.applicability:
            return []
        # Поддерживаем разные разделители: запятая, точка с запятой, перенос строки
        import re
        # Разбиваем по запятой, точке с запятой или переносу строки
        items = re.split(r'[,;\n]', self.applicability)
        result = [a.strip() for a in items if a.strip()]
        return result

    @property
    def has_discount(self):
        return self.old_price and self.old_price > self.price

    @property
    def discount_percent(self):
        if self.has_discount:
            return int((1 - self.price / self.old_price) * 100)
        return 0


def product_image_path(instance, filename):
    """Генерация пути для изображений товара."""
    ext = filename.split('.')[-1]
    filename = f'{instance.product.article or instance.product.pk}_{instance.pk or "new"}.{ext}'
    return os.path.join('products', str(instance.product.pk), filename)


class ProductImage(models.Model):
    """Изображения товара."""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='images',
        verbose_name='Товар'
    )
    image = models.ImageField('Изображение', upload_to='products/')
    alt = models.CharField('Alt текст', max_length=200, blank=True)
    is_main = models.BooleanField('Главное изображение', default=False)
    order = models.PositiveIntegerField('Порядок', default=0)
    created_at = models.DateTimeField('Загружено', auto_now_add=True)

    class Meta:
        verbose_name = 'Изображение товара'
        verbose_name_plural = 'Изображения товаров'
        ordering = ['-is_main', 'order']

    def __str__(self):
        return f'Изображение для {self.product.name}'

    def save(self, *args, **kwargs):
        # Если это главное изображение, убираем флаг у других
        if self.is_main:
            ProductImage.objects.filter(product=self.product, is_main=True).exclude(pk=self.pk).update(is_main=False)
        # Автоматический alt
        if not self.alt:
            self.alt = f'Фото {self.product.article} {self.product.brand}'.strip()
        super().save(*args, **kwargs)

    def get_image_url(self):
        """Возвращает полный URL изображения."""
        if self.image:
            return self.image.url
        return None


class Brand(models.Model):
    """Бренды товаров."""
    name = models.CharField('Название', max_length=200, unique=True)
    slug = models.SlugField('URL', max_length=200, unique=True, blank=True)
    logo = models.ImageField('Логотип', upload_to='brands/', blank=True, null=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = transliterate_slug(self.name)
        super().save(*args, **kwargs)


class ImportLog(models.Model):
    """Лог импорта товаров."""
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('partial', 'Частично'),
        ('error', 'Ошибка'),
    ]
    
    filename = models.CharField('Файл', max_length=255)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES)
    total_rows = models.PositiveIntegerField('Всего строк', default=0)
    imported_rows = models.PositiveIntegerField('Импортировано', default=0)
    error_rows = models.PositiveIntegerField('Ошибок', default=0)
    errors = models.TextField('Описание ошибок', blank=True)
    created_at = models.DateTimeField('Дата импорта', auto_now_add=True)
    user = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name='Пользователь'
    )

    class Meta:
        verbose_name = 'Лог импорта'
        verbose_name_plural = 'Логи импорта'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.filename} - {self.created_at}'


class OneCExchangeLog(models.Model):
    """Лог обмена данными с 1С через API."""
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
        ('unauthorized', 'Не авторизован'),
    ]
    
    request_method = models.CharField('Метод', max_length=10, default='POST')
    request_path = models.CharField('Путь', max_length=255)
    request_ip = models.GenericIPAddressField('IP адрес', null=True, blank=True)
    request_headers = models.JSONField('Заголовки запроса', default=dict, blank=True)
    request_body_size = models.PositiveIntegerField('Размер тела запроса (байт)', default=0)
    request_format = models.CharField('Формат данных', max_length=20, blank=True, help_text='XML или JSON')
    
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES)
    status_code = models.PositiveIntegerField('HTTP код ответа', default=200)
    
    total_products = models.PositiveIntegerField('Всего товаров в запросе', default=0)
    updated_products = models.PositiveIntegerField('Обновлено товаров', default=0)
    created_products = models.PositiveIntegerField('Создано товаров', default=0)
    hidden_products = models.PositiveIntegerField('Скрыто товаров', default=0)
    errors_count = models.PositiveIntegerField('Ошибок', default=0)
    
    error_message = models.TextField('Сообщение об ошибке', blank=True)
    response_data = models.JSONField('Данные ответа', default=dict, blank=True)
    
    processing_time = models.FloatField('Время обработки (сек)', default=0.0)
    created_at = models.DateTimeField('Дата обмена', auto_now_add=True)

    class Meta:
        verbose_name = 'Лог обмена с 1С'
        verbose_name_plural = 'Логи обмена с 1С'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['request_ip']),
        ]

    def __str__(self):
        return f'{self.request_path} - {self.status} - {self.created_at}'


class FarpostAPISettings(models.Model):
    """Настройки API Farpost для синхронизации товаров."""
    login = models.CharField('Логин', max_length=255, help_text='Логин для входа на Farpost')
    password = models.CharField('Пароль', max_length=255, help_text='Пароль (хранится в зашифрованном виде)')
    packet_id = models.CharField(
        'ID пакет-объявления', 
        max_length=50, 
        help_text='ID пакет-объявления на Farpost. Один пакет может содержать тысячи товаров из разных категорий. '
                  'Можно создать несколько настроек с разными packet_id для разделения товаров по пакетам. '
                  'ID можно найти в URL пакета: https://www.farpost.ru/personal/goods/packet/{id}/recurrent-update'
    )
    is_active = models.BooleanField('Активен', default=True, help_text='Использовать эти настройки для синхронизации')
    last_sync = models.DateTimeField('Последняя синхронизация', null=True, blank=True)
    last_sync_status = models.CharField('Статус последней синхронизации', max_length=50, blank=True)
    last_sync_error = models.TextField('Ошибка последней синхронизации', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        verbose_name = 'Настройки API Farpost'
        verbose_name_plural = 'Настройки API Farpost'
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        status = 'активен' if self.is_active else 'неактивен'
        return f'API Farpost ({self.login}) - {status}'
    
    def get_decrypted_password(self):
        """Получить расшифрованный пароль."""
        from django.core.signing import Signer
        from django.conf import settings
        try:
            signer = Signer(key=settings.SECRET_KEY)
            return signer.unsign(self.password)
        except Exception:
            return self.password
    
    def set_encrypted_password(self, password):
        """Сохранить пароль в зашифрованном виде."""
        from django.core.signing import Signer
        from django.conf import settings
        signer = Signer(key=settings.SECRET_KEY)
        self.password = signer.sign(password)


class Promotion(models.Model):
    """Акции и специальные предложения для главной страницы."""
    title = models.CharField('Заголовок', max_length=200, blank=True, help_text='Необязательно. Если не указан, будет использовано изображение.')
    image = models.ImageField('Изображение', upload_to='promotions/')
    link = models.URLField('Ссылка', blank=True, help_text='Куда ведёт акция (необязательно)')
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активна', default=True)
    order = models.PositiveIntegerField('Порядок сортировки', default=0)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Акция / Спец предложение'
        verbose_name_plural = 'Акции / Спец предложения'
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title or f'Акция #{self.pk}'