from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import pre_delete
from django.urls import reverse
from django.utils.text import slugify


def validate_hero_slide_image(image):
    """Проверка файла кадра карусели: формат и размер."""
    max_bytes = 8 * 1024 * 1024
    if getattr(image, 'size', 0) > max_bytes:
        from django.core.exceptions import ValidationError
        raise ValidationError('Размер файла не должен превышать 8 МБ.')
    name = (getattr(image, 'name', '') or '').lower()
    allowed = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
    if name and not name.endswith(allowed):
        from django.core.exceptions import ValidationError
        raise ValidationError('Допустимые форматы: JPG, PNG, WEBP, GIF.')


class Page(models.Model):
    """Редактируемые страницы сайта."""
    SLUG_CHOICES = [
        ('about', 'О компании'),
        ('payment-delivery', 'Оплата и доставка'),
        ('contacts', 'Контакты'),
        ('wholesale', 'Оптовые продажи'),
        ('public-offer', 'Не является публичной офертой'),
        ('privacy-policy', 'Политика конфиденциальности'),
        ('consent', 'Согласие на обработку персональных данных'),
    ]
    
    slug = models.CharField('Тип страницы', max_length=50, choices=SLUG_CHOICES, unique=True)
    title = models.CharField('Заголовок', max_length=200)
    content = models.TextField('Содержимое', help_text='HTML разметка разрешена')
    meta_title = models.CharField('Meta Title', max_length=200, blank=True)
    meta_description = models.TextField('Meta Description', blank=True)
    is_active = models.BooleanField('Активна', default=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)
    
    class Meta:
        verbose_name = 'Страница'
        verbose_name_plural = 'Страницы'
        ordering = ['slug']
    
    def __str__(self):
        return self.get_slug_display()
    
    def get_absolute_url(self):
        slug_map = {
            'about': 'core:about',
            'payment-delivery': 'core:payment_delivery',
            'contacts': 'core:contacts',
            'wholesale': 'core:wholesale',
            'public-offer': 'core:public_offer',
            'privacy-policy': 'core:privacy_policy',
            'consent': 'core:consent',
        }
        url_name = slug_map.get(self.slug)
        if url_name:
            try:
                return reverse(url_name)
            except Exception:
                return '/'
        return '/'


class HeroCarouselSettings(models.Model):
    """Единственная запись с параметрами карусели на главной."""

    interval_seconds = models.PositiveSmallIntegerField(
        'Скорость слайдшоу, сек',
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
        help_text='Через сколько секунд автоматически показывать следующее изображение. От 1 до 120.',
    )
    visible_count = models.PositiveSmallIntegerField(
        'Количество изображений',
        default=0,
        validators=[MaxValueValidator(50)],
        help_text=(
            'Сколько активных изображений показывать на главной. '
            'Берутся первые по порядку. 0 — показывать все активные.'
        ),
    )
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Настройки карусели'
        verbose_name_plural = 'Настройки карусели'

    def __str__(self):
        if self.visible_count:
            count_label = f'{self.visible_count} изобр.'
        else:
            count_label = 'все активные'
        return f'Карусель: {self.interval_seconds} сек, {count_label}'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            obj = cls.objects.create(pk=1)
        return obj


class HeroSlide(models.Model):
    """Изображение карусели на главной странице."""

    image = models.ImageField(
        'Изображение',
        upload_to='hero/',
        validators=[validate_hero_slide_image],
        help_text='Любой размер. Картинка целиком помещается в блок, без обрезки. JPG, PNG, WEBP или GIF, до 8 МБ. Новая загрузка заменяет текущий файл.',
    )
    alt = models.CharField(
        'Подпись',
        max_length=200,
        blank=True,
        help_text='Краткое описание изображения. Если пусто, на сайте подставится название компании.',
    )
    is_active = models.BooleanField(
        'Показывать на сайте',
        default=True,
        help_text='Снимите галочку, чтобы временно убрать изображение из карусели, не удаляя файл.',
    )
    order = models.PositiveIntegerField(
        'Порядок',
        default=0,
        help_text='Меньшее число показывается раньше. Одинаковые значения идут по порядку добавления.',
    )
    created_at = models.DateTimeField('Добавлено', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Изображение карусели'
        verbose_name_plural = 'Изображения карусели'
        ordering = ['order', 'id']

    def __str__(self):
        return self.alt or f'Изображение #{self.pk or "новое"}'

    def save(self, *args, **kwargs):
        previous_name = ''
        if self.pk:
            previous_name = (
                HeroSlide.objects.filter(pk=self.pk)
                .values_list('image', flat=True)
                .first()
                or ''
            )
        super().save(*args, **kwargs)
        current_name = self.image.name if self.image else ''
        if previous_name and current_name and previous_name != current_name:
            self.image.storage.delete(previous_name)


def _delete_hero_slide_file(sender, instance, **kwargs):
    name = instance.image.name if instance.image else ''
    if name:
        instance.image.storage.delete(name)


pre_delete.connect(_delete_hero_slide_file, sender=HeroSlide)

