# Диагностика проблемы с offers.xml

## Проблема
Товары из offers.xml не появляются на сайте, хотя в файле есть цены и остатки.

## Возможные причины

### 1. Товары не созданы из import.xml
**Проверка:**
```bash
# На сервере проверьте логи обработки файлов
tail -f /path/to/logs/django.log | grep -i "import\|offers"

# Или проверьте в админке Django:
# - Перейдите в "Логи синхронизации" (SyncLog)
# - Проверьте, обработан ли import.xml
# - Проверьте, сколько товаров создано
```

**Решение:**
- Убедитесь, что `import.xml` обработан ПЕРЕД `offers.xml`
- Проверьте, что товары созданы с правильным `external_id`

### 2. Несовпадение external_id между import.xml и offers.xml
**Проверка:**
```python
# В Django shell на сервере
from catalog.models import Product

# Проверьте, есть ли товары в базе
print(f"Всего товаров: {Product.objects.count()}")
print(f"Товаров в retail: {Product.objects.filter(catalog_type='retail').count()}")
print(f"Товаров в wholesale: {Product.objects.filter(catalog_type='wholesale').count()}")

# Проверьте несколько товаров
products = Product.objects.all()[:5]
for p in products:
    print(f"ID: {p.external_id}, Артикул: {p.article}, Название: {p.name[:50]}, Цена: {p.price}, Остаток: {p.quantity}, Активен: {p.is_active}")
```

### 3. Неправильное определение catalog_type для offers.xml
**Проверка:**
- Имя файла offers.xml должно содержать ключевые слова для опта: `wholesale`, `опт`, `opt`, `партнер`, `partner`
- Или тип цены в файле должен содержать эти ключевые слова

**Решение:**
- Если offers.xml для розницы, убедитесь, что имя файла НЕ содержит ключевых слов опта
- Если offers.xml для опта, убедитесь, что имя файла содержит ключевые слова опта

### 4. Товары не активны (is_active=False)
**Проверка:**
```python
# В Django shell
from catalog.models import Product

# Проверьте неактивные товары
inactive = Product.objects.filter(is_active=False)
print(f"Неактивных товаров: {inactive.count()}")

# Проверьте товары без цены
no_price = Product.objects.filter(price=0, wholesale_price=0)
print(f"Товаров без цены: {no_price.count()}")

# Проверьте товары с ценой, но неактивные
with_price_inactive = Product.objects.filter(is_active=False).exclude(price=0).exclude(wholesale_price=0)
print(f"Товаров с ценой, но неактивных: {with_price_inactive.count()}")
```

## Команды для проверки на сервере

### 1. Проверить логи обработки
```bash
# Найдите последние логи обработки файлов
grep -i "offers\|import" /path/to/logs/django.log | tail -50

# Или если логи в другом месте
journalctl -u your-django-service | grep -i "offers\|import" | tail -50
```

### 2. Проверить товары в базе
```bash
# В Django shell
python manage.py shell

from catalog.models import Product
# Проверьте статистику
print(f"Всего: {Product.objects.count()}")
print(f"Retail: {Product.objects.filter(catalog_type='retail').count()}")
print(f"Wholesale: {Product.objects.filter(catalog_type='wholesale').count()}")
print(f"С ценой: {Product.objects.exclude(price=0).exclude(wholesale_price=0).count()}")
print(f"Активных: {Product.objects.filter(is_active=True).count()}")
print(f"С остатком: {Product.objects.filter(quantity__gt=0).count()}")
```

### 3. Проверить конкретный товар
```python
# В Django shell
from catalog.models import Product

# Найдите товар по external_id из offers.xml
external_id = "ваш_external_id_из_offers"
product = Product.objects.filter(external_id=external_id).first()
if product:
    print(f"Найден: {product.name}, каталог: {product.catalog_type}, цена: {product.price}, оптовая: {product.wholesale_price}, остаток: {product.quantity}, активен: {product.is_active}")
else:
    print("Товар не найден!")
```

## Что было исправлено в коде

1. **Улучшен поиск товаров в offers.xml:**
   - Теперь ищет товары во всех каталогах, не только в нужном
   - Если товар найден в другом каталоге, создает копию в нужном

2. **Улучшена логика активности товаров:**
   - Товар активен, если есть цена ИЛИ остаток
   - Товары с ценой, но без остатка, отображаются как "под заказ"

3. **Добавлено логирование:**
   - Логируется количество найденных предложений
   - Логируется количество товаров в базе
   - Логируются предупреждения о ненайденных товарах

## Рекомендации

1. **Порядок обработки файлов:**
   - Сначала обработайте `import.xml` (создает товары)
   - Затем обработайте `offers.xml` (обновляет цены и остатки)

2. **Проверьте логи:**
   - После обработки проверьте логи на наличие предупреждений
   - Обратите внимание на сообщения "Товар с Ид ... не найден в базе"

3. **Проверьте товары в админке:**
   - Убедитесь, что товары созданы с правильным `external_id`
   - Проверьте, что товары имеют цены и остатки после обработки offers.xml
