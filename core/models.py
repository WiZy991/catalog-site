from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Page(models.Model):
    """Редактируемые страницы сайта."""
    SLUG_CHOICES = [
        ('about', 'О компании'),
        ('payment-delivery', 'Оплата и доставка'),
        ('contacts', 'Контакты'),
        ('wholesale', 'Оптовые продажи'),
        ('public-offer', 'Не является публичной офертой'),
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
        }
        url_name = slug_map.get(self.slug, 'core:home')
        return reverse(url_name)

