# Исправление ошибки в catalog/sitemaps.py

## Проблема
На сервере в файле `catalog/sitemaps.py` остались маркеры конфликта слияния Git:
```
>>>>>>> 20d0f6a9b78de8c6c25ef4c1277072bab3ab3c52
```

## Решение

### Вариант 1: Заменить файл на сервере

Подключитесь к серверу и замените содержимое файла:

```bash
cd ~/onesimus/onesimus
nano catalog/sitemaps.py
```

Удалите все маркеры конфликта (строки с `<<<<<<<`, `=======`, `>>>>>>>`) и оставьте только правильный код:

```python
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Category


class ProductSitemap(Sitemap):
    """Sitemap для товаров."""
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Product.objects.filter(
            is_active=True,
            quantity__gt=0  # Только товары с остатком
        ).select_related('category')

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    """Sitemap для категорий."""
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class StaticViewSitemap(Sitemap):
    """Sitemap для статических страниц."""
    priority = 1.0
    changefreq = 'monthly'

    def items(self):
        return [
            'core:home',
            'catalog:index',
            'core:contacts',
            'core:about',
            'core:payment_delivery',
            'core:wholesale',
            'core:privacy_policy',
            'core:consent',
            'core:public_offer',
        ]

    def location(self, item):
        return reverse(item)
```

### Вариант 2: Использовать sed для автоматического удаления

```bash
cd ~/onesimus/onesimus
sed -i '/^<<<<<<</,/^>>>>>>>/d' catalog/sitemaps.py
```

### Вариант 3: Синхронизировать с локальной версией

Если у вас есть правильная версия локально, загрузите её на сервер через SFTP или скопируйте содержимое.

## После исправления

1. Перезапустите приложение:
```bash
touch tmp/restart.txt
```

2. Проверьте логи:
```bash
tail -f logs/django.log
```

3. Проверьте сайт:
```bash
curl -I http://onesim8n.beget.tech/
```

## Проверка синтаксиса

Перед перезапуском проверьте синтаксис:
```bash
python3 -m py_compile catalog/sitemaps.py
```

Если ошибок нет, команда ничего не выведет.
