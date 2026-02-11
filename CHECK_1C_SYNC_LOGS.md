# Проверка логов синхронизации с 1С

## Где смотреть логи

### 1. В админ-панели Django

1. Зайдите в админ-панель: `http://onesim8n.beget.tech/admin/`
2. Перейдите в раздел **Catalog** → **Sync logs** (Логи синхронизации 1С)
3. Откройте последнюю запись

**Что смотреть:**
- **Статус** - должен быть "Успешно" или "Частично успешно"
- **Обработано товаров** - сколько товаров было в файле
- **Создано товаров** - сколько новых товаров создано
- **Обновлено товаров** - сколько существующих товаров обновлено
- **Ошибок** - количество ошибок
- **Ошибки** (вкладка) - детали ошибок, если есть

### 2. На сервере через командную строку

```bash
cd ~/onesimus/onesimus

# Проверить последние логи через Django shell
python manage.py shell
```

В shell:
```python
from catalog.models import SyncLog
from django.utils import timezone
from datetime import timedelta

# Последние 5 логов
logs = SyncLog.objects.all()[:5]
for log in logs:
    print(f"\n=== Лог от {log.created_at} ===")
    print(f"Тип: {log.get_operation_type_display()}")
    print(f"Статус: {log.get_status_display()}")
    print(f"Обработано: {log.processed_count}")
    print(f"Создано: {log.created_count}")
    print(f"Обновлено: {log.updated_count}")
    print(f"Ошибок: {log.errors_count}")
    print(f"Файл: {log.filename}")
    if log.errors:
        print(f"Ошибки: {log.errors}")
```

### 3. Проверка файлов обмена

```bash
# Проверить, какие файлы были загружены
ls -lah ~/onesimus/onesimus/media/1c_exchange/

# Посмотреть содержимое последнего файла (первые 50 строк)
ls -t ~/onesimus/onesimus/media/1c_exchange/*.xml 2>/dev/null | head -1 | xargs head -50
```

### 4. Проверка товаров в базе

```bash
python manage.py shell
```

В shell:
```python
from catalog.models import Product

# Проверить последние созданные товары
recent_products = Product.objects.filter(external_id__isnull=False).order_by('-id')[:10]
for p in recent_products:
    print(f"{p.id}. {p.name} (артикул: {p.article}, external_id: {p.external_id}, активен: {p.is_active})")

# Проверить количество товаров с external_id
total = Product.objects.filter(external_id__isnull=False).count()
print(f"\nВсего товаров с external_id: {total}")
```

## Диагностика проблем

### Проблема: "Обработано: 0"

**Причины:**
- Файл не содержит товаров в ожидаемом формате
- Неправильный namespace в XML
- Товары находятся в другом месте структуры XML

**Решение:**
1. Проверьте содержимое файла CommerceML
2. Проверьте логи Django на сервере
3. Убедитесь, что файл содержит элементы `<Товар>` или `<catalog:Товар>`

### Проблема: "Обработано: X, но товары не видны на сайте"

**Причины:**
- Товары созданы, но `is_active=False`
- Товары не привязаны к категориям
- Фильтры на сайте скрывают товары

**Решение:**
```python
# Проверить активность товаров
from catalog.models import Product
inactive = Product.objects.filter(external_id__isnull=False, is_active=False).count()
print(f"Неактивных товаров: {inactive}")

# Активировать все товары из 1С
Product.objects.filter(external_id__isnull=False, is_active=False).update(is_active=True)
```

### Проблема: "Ошибки при обработке"

**Решение:**
1. Откройте лог в админке
2. Посмотрите вкладку "Ошибки"
3. Исправьте проблемы в данных 1С
4. Повторите обмен

## Добавлено подробное логирование

Теперь в коде добавлено подробное логирование:
- Размер файла
- Количество найденных элементов
- Детали обработки каждого товара
- Все ошибки с деталями

Логи можно посмотреть в:
- Админ-панели Django (Sync logs)
- Логах Django на сервере (если настроены)
