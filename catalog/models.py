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
    
    # Ключевые слова для автоматического распределения товаров
    keywords = models.TextField(
        'Ключевые слова', 
        blank=True,
        help_text='Слова для автоопределения категории (через запятую). '
                  'Пример: стартер, генератор, датчик, реле'
    )
    
    meta_title = models.CharField('Meta Title', max_length=200, blank=True)
    meta_description = models.TextField('Meta Description', blank=True)
    seo_text = models.TextField('SEO текст', blank=True)
    is_active = models.BooleanField('Активна', default=True)
    order = models.PositiveIntegerField('Порядок сортировки', default=0)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = transliterate_slug(self.name)
            slug = base_slug
            counter = 1
            # Проверяем уникальность slug
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        ancestors = self.get_ancestors(include_self=True)
        path = '/'.join([cat.slug for cat in ancestors])
        return reverse('catalog:category', kwargs={'path': path})

    def get_meta_title(self):
        return self.meta_title or f'{self.name} - купить в каталоге'

    def get_meta_description(self):
        return self.meta_description or f'Каталог {self.name.lower()}. Большой выбор, доступные цены.'

    def get_keywords_list(self):
        """Возвращает список ключевых слов для автоопределения категории."""
        if not self.keywords:
            return []
        return [k.strip().lower() for k in self.keywords.split(',') if k.strip()]

    @property
    def product_count(self):
        """Количество товаров в категории и её подкатегориях (только retail)."""
        # Если уже посчитано (например, в HomeView), используем кэшированное значение
        if hasattr(self, '_product_count'):
            return self._product_count
        
        # ВАЖНО: НЕ используем кеширование - всегда получаем актуальные данные из БД
        # Это гарантирует, что количество товаров всегда корректное
        descendants = self.get_descendants(include_self=True)
        # Преобразуем QuerySet в список ID для более надежной работы
        descendant_ids = list(descendants.values_list('id', flat=True))
        if not descendant_ids:
            return 0
        
        count = Product.objects.filter(
            category_id__in=descendant_ids,
            is_active=True,
            catalog_type='retail',
            quantity__gt=0,
        ).count()
        
        return count


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
    
    CATALOG_TYPE_CHOICES = [
        ('retail', 'Основной каталог'),
        ('wholesale', 'Партнёрский каталог'),
    ]

    # Тип каталога
    catalog_type = models.CharField(
        'Каталог', 
        max_length=20, 
        choices=CATALOG_TYPE_CHOICES, 
        default='retail',
        db_index=True,
        help_text='retail = основной сайт, wholesale = только для партнёров'
    )

    # Основные поля
    name = models.CharField('Название', max_length=500)
    slug = models.SlugField('URL', max_length=500, unique=True, blank=True)
    external_id = models.CharField('ID из 1С', max_length=255, blank=True, null=True, db_index=True, help_text='Уникальный идентификатор товара из 1С (уникален в комбинации с catalog_type)')
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
    price = models.DecimalField('Цена (розница)', max_digits=12, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(
        'Оптовая цена', 
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text='Цена для партнёров. Если не указана, будет равна розничной цене.'
    )
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
        unique_together = [['external_id', 'catalog_type']]
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
        """Получить главное изображение товара.
        Для оптовых товаров без собственных фото берём фото из розничного аналога.
        """
        main = self.images.filter(is_main=True).first()
        if main:
            return main
        first = self.images.first()
        if first:
            return first
        # Фоллбэк: если это оптовый товар без фото, ищем фото у розничного аналога
        if self.catalog_type == 'wholesale' and self.external_id:
            retail = Product.objects.filter(
                external_id=self.external_id,
                catalog_type='retail'
            ).first()
            if retail:
                main = retail.images.filter(is_main=True).first()
                if main:
                    return main
                return retail.images.first()
        return None

    def get_all_images(self):
        """Получить все изображения товара.
        Для оптовых товаров без собственных фото берём фото из розничного аналога.
        """
        own_images = self.images.all().order_by('-is_main', 'order')
        if own_images.exists():
            return own_images
        # Фоллбэк: если это оптовый товар без фото, ищем фото у розничного аналога
        if self.catalog_type == 'wholesale' and self.external_id:
            retail = Product.objects.filter(
                external_id=self.external_id,
                catalog_type='retail'
            ).first()
            if retail:
                return retail.images.all().order_by('-is_main', 'order')
        return own_images

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
        """Преобразует характеристики в список кортежей (ключ, значение) с фильтрацией."""
        if not self.characteristics:
            return []
        result = []
        import re
        
        # Исключаем материалы и другие ненужные характеристики
        excluded_keys = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
        
        for line in self.characteristics.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key_stripped = key.strip()
                value_stripped = value.strip()
                key_lower = key_stripped.lower()
                
                # Пропускаем материалы и другие ненужные характеристики
                if any(excluded in key_lower for excluded in excluded_keys):
                    continue
                
                # ВАЖНО: "Размер" всегда должен попадать в характеристики БЕЗ фильтрации!
                # Значение может быть любым: "12V/80А/ПЛ. РЕМ.5Д/ОВ.Ф./ЗКОНТ", "20*450" и т.д.
                if 'размер' not in key_lower and 'size' not in key_lower:
                    # Проверяем, что значение не является кодом модели/применимости
                    # Коды моделей обычно: 1-4 цифры + буквы (например, 1GEN, 1NZF, 2GR, 4AFE)
                    # Или только буквы+цифры без * или x
                    if re.match(r'^[A-Z0-9#\-/]{1,10}$', value_stripped.upper()) and not re.search(r'[*x]', value_stripped):
                        # Это похоже на код модели, а не на характеристику
                        # Проверяем, не является ли это применимостью
                        if self.applicability and value_stripped.upper() in self.applicability.upper():
                            # Это применимость, не характеристика
                            continue
                
                result.append((key_stripped, value_stripped))
        
        return result

    def get_cross_numbers_list(self):
        """Преобразует кросс-номера в список."""
        if not self.cross_numbers:
            return []
        return [n.strip() for n in self.cross_numbers.split(',') if n.strip()]

    def get_applicability_list(self):
        """Преобразует применимость в список, исключая вольтаж и длинные описания."""
        if not self.applicability:
            return []
        # Поддерживаем разные разделители: запятая, точка с запятой, перенос строки
        import re
        # Разбиваем по запятой, точке с запятой или переносу строки
        items = re.split(r'[,;\n]', self.applicability)
        result = []
        # Паттерн для вольтажа: 14V-12V, 12V-11V, 14V, 12V и т.д.
        voltage_pattern = re.compile(r'^\s*\d+V(?:-\d+V)?\s*$', re.IGNORECASE)
        for item in items:
            item_stripped = item.strip()
            if item_stripped:
                # Пропускаем элементы, которые являются вольтажем
                if voltage_pattern.match(item_stripped):
                    continue
                # Пропускаем слишком длинные элементы (это описания, а не применимость)
                # Применимость обычно короткая: коды моделей, двигателей (1GEN, 1NZF, 2GR и т.д.)
                if len(item_stripped) > 50:
                    # Слишком длинное - это описание, не применимость
                    continue
                # Пропускаем элементы, которые содержат много слов (это описания)
                word_count = len(item_stripped.split())
                if word_count > 5:
                    # Слишком много слов - это описание, не применимость
                    continue
                result.append(item_stripped)
        return result
    
    def get_voltage_from_applicability(self):
        """Извлекает вольтаж из применимости для перемещения в характеристики."""
        if not self.applicability:
            return None
        import re
        # Паттерн для вольтажа: 14V-12V, 12V-11V, 14V, 12V и т.д.
        voltage_match = re.search(r'\b(\d+V(?:-\d+V)?)\b', self.applicability, re.IGNORECASE)
        if voltage_match:
            return voltage_match.group(1).upper()
        return None

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
    from django.utils.text import get_valid_filename
    ext = filename.split('.')[-1]
    safe_name = get_valid_filename(f'{instance.product.article or instance.product.pk}_{instance.pk or "new"}.{ext}')
    return os.path.join('products', str(instance.product.pk), safe_name)


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


class ProductCharacteristic(models.Model):
    """Характеристика товара."""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='product_characteristics',
        verbose_name='Товар'
    )
    name = models.CharField('Название характеристики', max_length=200)
    value = models.CharField('Значение', max_length=500)
    order = models.PositiveIntegerField('Порядок сортировки', default=0)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Характеристика товара'
        verbose_name_plural = 'Характеристики товаров'
        ordering = ['order', 'name']
        unique_together = [['product', 'name']]
        indexes = [
            models.Index(fields=['product', 'name']),
        ]

    def __str__(self):
        return f'{self.product.name} - {self.name}: {self.value}'


class SyncLog(models.Model):
    """Лог синхронизации товаров с 1С."""
    OPERATION_TYPE_CHOICES = [
        ('file_upload', 'Загрузка файла'),
        ('api_sync', 'API синхронизация'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('partial', 'Частично'),
        ('error', 'Ошибка'),
        ('unauthorized', 'Не авторизован'),
    ]
    
    operation_type = models.CharField(
        'Тип операции',
        max_length=20,
        choices=OPERATION_TYPE_CHOICES,
        default='api_sync'
    )
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES)
    message = models.TextField('Сообщение', blank=True)
    processed_count = models.PositiveIntegerField('Обработано товаров', default=0)
    created_count = models.PositiveIntegerField('Создано товаров', default=0)
    updated_count = models.PositiveIntegerField('Обновлено товаров', default=0)
    errors_count = models.PositiveIntegerField('Ошибок', default=0)
    errors = models.JSONField('Список ошибок', default=list, blank=True)
    
    # Метаданные запроса
    request_ip = models.GenericIPAddressField('IP адрес', null=True, blank=True)
    request_format = models.CharField('Формат данных', max_length=20, blank=True, help_text='CSV, XML или JSON')
    filename = models.CharField('Имя файла', max_length=255, blank=True)
    
    created_at = models.DateTimeField('Дата синхронизации', auto_now_add=True)
    processing_time = models.FloatField('Время обработки (сек)', default=0.0)

    class Meta:
        verbose_name = 'Лог синхронизации'
        verbose_name_plural = 'Логи синхронизации'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['operation_type']),
        ]

    def __str__(self):
        return f'{self.get_operation_type_display()} - {self.status} - {self.created_at}'


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
    login = models.CharField('Логин', max_length=255, blank=True, help_text='Логин для входа на Farpost (необязательно, если используется ключ)')
    password = models.CharField('Пароль', max_length=255, blank=True, help_text='Пароль (хранится в зашифрованном виде, необязательно если используется ключ)')
    api_key = models.CharField(
        'Ключ API', 
        max_length=255, 
        blank=True,
        help_text='Ключ для аутентификации в API Farpost. Предоставляется Farpost по запросу. '
                  'Используется для расчета auth (SHA512 от ключа). Если указан, имеет приоритет над login:password.'
    )
    packet_id = models.CharField(
        'ID пакет-объявления', 
        max_length=50, 
        blank=True,
        null=True,
        default='',
        help_text='ID пакет-объявления на Farpost (необязательно). '
                  'ID можно найти в URL пакета: https://www.farpost.ru/personal/goods/packet/{id}/recurrent-update'
    )
    
    # Настройки автоматического обновления
    auto_update_enabled = models.BooleanField(
        'Автоматическое обновление', 
        default=False,
        help_text='Включить периодическое автоматическое обновление прайс-листа по ссылке'
    )
    auto_update_url = models.URLField(
        'Ссылка на прайс-лист', 
        blank=True,
        help_text='URL для автоматического обновления прайс-листа. Например: http://site.ru/import-price/new-price.csv'
    )
    auto_update_interval = models.PositiveIntegerField(
        'Интервал обновления (часы)', 
        default=24,
        help_text='Как часто обновлять прайс-лист (в часах). Минимум: 1 час.'
    )
    last_auto_update = models.DateTimeField('Последнее автоматическое обновление', null=True, blank=True)
    
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
        if not self.password:
            return ''
        from django.core.signing import Signer
        from django.conf import settings
        try:
            signer = Signer(key=settings.SECRET_KEY)
            return signer.unsign(self.password)
        except Exception:
            return self.password
    
    def set_encrypted_password(self, password):
        """Сохранить пароль в зашифрованном виде."""
        if not password:
            self.password = ''
            return
        from django.core.signing import Signer
        from django.conf import settings
        signer = Signer(key=settings.SECRET_KEY)
        self.password = signer.sign(password)
    
    def get_decrypted_api_key(self):
        """Получить расшифрованный ключ API."""
        if not self.api_key:
            return ''
        from django.core.signing import Signer
        from django.conf import settings
        try:
            signer = Signer(key=settings.SECRET_KEY)
            return signer.unsign(self.api_key)
        except Exception:
            return self.api_key
    
    def set_encrypted_api_key(self, api_key):
        """Сохранить ключ API в зашифрованном виде."""
        if not api_key:
            self.api_key = ''
            return
        from django.core.signing import Signer
        from django.conf import settings
        signer = Signer(key=settings.SECRET_KEY)
        self.api_key = signer.sign(api_key)
    
    def get_auth_hash(self):
        """
        Получить хеш для аутентификации в API Farpost.
        Согласно инструкции: auth = hash('sha512', X), где X - строка с ключом.
        Если ключ указан, используем его. Иначе используем login:password (для обратной совместимости).
        """
        import hashlib
        api_key = self.get_decrypted_api_key()
        if api_key:
            # Используем ключ API (предпочтительный способ согласно инструкции)
            auth_string = api_key
        elif self.login and self.password:
            # Обратная совместимость: используем login:password
            password = self.get_decrypted_password()
            auth_string = f'{self.login}:{password}'
        else:
            raise ValueError('Не указан ключ API или логин/пароль для аутентификации')
        
        return hashlib.sha512(auth_string.encode('utf-8')).hexdigest()


class Promotion(models.Model):
    """Акции и специальные предложения для главной страницы."""
    title = models.CharField('Заголовок', max_length=200, blank=True, help_text='Необязательно. Если не указан, будет использовано изображение.')
    image = models.ImageField('Изображение', upload_to='promotions/', blank=True, null=True)
    video = models.FileField('Видео-ролик', upload_to='promotions/videos/', blank=True, null=True, help_text='Необязательно. Если загружено видео — на сайте будет показано видео вместо изображения.')
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

    def has_video(self) -> bool:
        return bool(self.video)


class WholesaleProduct(Product):
    """Proxy-модель для импорта/экспорта оптовых цен.
    
    Используется для отдельного импорта товаров в партнёрский раздел
    с оптовыми ценами, без влияния на основной каталог.
    """
    class Meta:
        proxy = True
        app_label = 'partners'
        verbose_name = 'Оптовый товар'
        verbose_name_plural = 'Оптовые товары (импорт для партнёров)'