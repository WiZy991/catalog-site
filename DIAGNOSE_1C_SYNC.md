# Диагностика обмена с 1С - пошаговая инструкция

## Проблема
1С сообщает об успешном обмене, но товары не появляются на сайте.

## Шаг 1: Проверка логов в админ-панели Django

1. Зайдите в админ-панель: `http://onesim8n.beget.tech/admin/`
2. Перейдите в раздел **Catalog** → **Sync logs** (Логи синхронизации 1С)
3. Найдите последнюю запись (самая свежая по дате)
4. Откройте её и проверьте:

**Что смотреть:**
- **Статус** - какой статус? (Успешно / Частично успешно / Ошибка)
- **Обработано товаров** - сколько товаров было обработано?
- **Создано товаров** - сколько новых товаров создано?
- **Обновлено товаров** - сколько существующих товаров обновлено?
- **Ошибок** - есть ли ошибки?
- **Ошибки** (вкладка внизу) - какие именно ошибки?

**Если "Обработано: 0"** - значит файл не содержит товаров или они в неправильном формате.

**Если "Обработано: X, но Создано: 0 и Обновлено: 0"** - значит товары найдены, но не обрабатываются (ошибки валидации).

## Шаг 2: Проверка через командную строку на сервере

Выполните на сервере:

```bash
cd ~/onesimus/onesimus
python manage.py shell
```

Затем в shell:

```python
from catalog.models import SyncLog
from django.utils import timezone
from datetime import timedelta

# Последние 3 лога
logs = SyncLog.objects.all()[:3]
for log in logs:
    print(f"\n{'='*60}")
    print(f"Лог от: {log.created_at}")
    print(f"Тип операции: {log.get_operation_type_display()}")
    print(f"Статус: {log.get_status_display()}")
    print(f"Файл: {log.filename}")
    print(f"Обработано товаров: {log.processed_count}")
    print(f"Создано товаров: {log.created_count}")
    print(f"Обновлено товаров: {log.updated_count}")
    print(f"Ошибок: {log.errors_count}")
    print(f"Время обработки: {log.processing_time} сек")
    
    if log.errors:
        print(f"\nОшибки:")
        for error in log.errors[:5]:  # Первые 5 ошибок
            print(f"  - {error}")
```

## Шаг 3: Проверка загруженных файлов

```bash
# Проверить, какие файлы были загружены
ls -lah ~/onesimus/onesimus/media/1c_exchange/

# Посмотреть последний файл (если есть)
ls -t ~/onesimus/onesimus/media/1c_exchange/*.xml 2>/dev/null | head -1
```

## Шаг 4: Проверка содержимого файла CommerceML

```bash
# Посмотреть первые 100 строк последнего файла
LAST_FILE=$(ls -t ~/onesimus/onesimus/media/1c_exchange/*.xml 2>/dev/null | head -1)
if [ -n "$LAST_FILE" ]; then
    echo "Файл: $LAST_FILE"
    head -100 "$LAST_FILE"
else
    echo "Файлы не найдены"
fi
```

## Шаг 5: Проверка товаров в базе данных

```python
from catalog.models import Product

# Проверить последние созданные товары с external_id
recent = Product.objects.filter(external_id__isnull=False).order_by('-id')[:10]
print(f"Последние 10 товаров с external_id:")
for p in recent:
    print(f"  {p.id}. {p.name[:50]} (артикул: {p.article}, external_id: {p.external_id}, активен: {p.is_active}, цена: {p.price})")

# Общая статистика
total_with_external = Product.objects.filter(external_id__isnull=False).count()
total_active = Product.objects.filter(external_id__isnull=False, is_active=True).count()
print(f"\nВсего товаров с external_id: {total_with_external}")
print(f"Активных товаров с external_id: {total_active}")
```

## Шаг 6: Проверка структуры XML файла

Если файлы есть, проверьте структуру:

```bash
python manage.py shell
```

```python
import xml.etree.ElementTree as ET
import os

# Найти последний файл
exchange_dir = os.path.join('media', '1c_exchange')
if os.path.exists(exchange_dir):
    files = sorted([f for f in os.listdir(exchange_dir) if f.endswith('.xml')], 
                   key=lambda x: os.path.getmtime(os.path.join(exchange_dir, x)), 
                   reverse=True)
    if files:
        last_file = os.path.join(exchange_dir, files[0])
        print(f"Анализ файла: {last_file}")
        
        tree = ET.parse(last_file)
        root = tree.getroot()
        
        print(f"\nКорневой элемент: {root.tag}")
        print(f"Дочерние элементы: {[child.tag for child in root]}")
        
        # Ищем каталог
        catalog = root.find('.//Каталог') or root.find('.//catalog')
        if catalog is not None:
            print(f"\nКаталог найден: {catalog.tag}")
            # Ищем товары
            products = catalog.findall('.//Товар') or catalog.findall('.//catalog:Товар')
            print(f"Найдено товаров: {len(products)}")
            
            if products:
                # Показываем первый товар
                first = products[0]
                print(f"\nПервый товар:")
                for child in first:
                    print(f"  {child.tag}: {child.text[:50] if child.text else 'None'}")
        else:
            print("\nКаталог не найден!")
```

## Шаг 7: Проверка логов Django на сервере

```bash
# Проверить логи Django (если настроены)
tail -100 ~/logs/django.log 2>/dev/null | grep -i "commerceml\|1c\|sync" || echo "Логи не найдены"

# Или проверить системные логи
journalctl -u django -n 50 2>/dev/null || echo "Systemd логи не найдены"
```

## Частые проблемы и решения

### Проблема 1: "Обработано: 0"

**Причина:** Файл не содержит товаров в ожидаемом формате.

**Решение:**
- Проверьте структуру XML файла (шаг 6)
- Убедитесь, что файл содержит элементы `<Товар>` или `<catalog:Товар>`
- Возможно, товары находятся в другом месте структуры

### Проблема 2: "Обработано: X, но Создано: 0"

**Причина:** Товары найдены, но не проходят валидацию.

**Решение:**
- Проверьте вкладку "Ошибки" в логе
- Убедитесь, что у товаров есть обязательные поля: `Ид` (или `Артикул`), `Наименование`, `Цена`

### Проблема 3: "Создано: X, но товары не видны на сайте"

**Причина:** Товары созданы, но неактивны или не привязаны к категориям.

**Решение:**
```python
# Активировать все товары из 1С
from catalog.models import Product
Product.objects.filter(external_id__isnull=False, is_active=False).update(is_active=True)
```

### Проблема 4: Файлы не загружаются

**Причина:** Ошибка на этапе загрузки файла.

**Решение:**
- Проверьте права на запись в директорию `media/1c_exchange/`
- Проверьте логи на ошибки при загрузке

## Быстрая проверка

Выполните все команды из шагов 2, 5 и 6 и пришлите результаты - это поможет точно определить проблему.
