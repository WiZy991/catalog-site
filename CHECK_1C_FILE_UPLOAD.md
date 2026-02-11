# Проверка загрузки файлов от 1С

## Проблема
Логов нет, файлов нет - значит файлы не загружаются или не обрабатываются.

## Диагностика

### Шаг 1: Проверка, что запросы доходят до сервера

После выполнения обмена в 1С, проверьте логи Django:

```bash
cd ~/onesimus/onesimus

# Проверить логи Django (если настроены)
tail -100 ~/logs/django.log 2>/dev/null | grep -i "commerceml\|1c\|handle_file\|handle_import" || echo "Логи не найдены"

# Или проверить через Python
python manage.py shell
```

В shell:
```python
import logging
# Найти все логгеры
loggers = [name for name in logging.Logger.manager.loggerDict]
print("Логгеры:", [l for l in loggers if 'catalog' in l or 'commerce' in l])
```

### Шаг 2: Проверка директории обмена

```bash
# Проверить, что директория существует и доступна для записи
ls -la ~/onesimus/onesimus/media/1c_exchange/
# Если директории нет, создайте её
mkdir -p ~/onesimus/onesimus/media/1c_exchange
chmod 755 ~/onesimus/onesimus/media/1c_exchange
```

### Шаг 3: Проверка через тестовый запрос

После выполнения обмена в 1С, сразу проверьте:

```bash
# Проверить, появились ли файлы
ls -lah ~/onesimus/onesimus/media/1c_exchange/

# Проверить логи синхронизации
python manage.py shell
```

В shell:
```python
from catalog.models import SyncLog
print(f"Всего логов: {SyncLog.objects.count()}")
```

### Шаг 4: Проверка прав доступа

```bash
# Проверить права на директорию media
ls -ld ~/onesimus/onesimus/media/
ls -ld ~/onesimus/onesimus/media/1c_exchange/ 2>/dev/null || echo "Директория не существует"

# Проверить, кто владелец
whoami
```

### Шаг 5: Ручная проверка загрузки файла

Попробуйте вручную загрузить тестовый файл:

```bash
# Создать тестовый XML файл
cat > /tmp/test.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация>
  <Каталог>
    <Товар>
      <Ид>TEST001</Ид>
      <Артикул>TEST001</Артикул>
      <Наименование>Тестовый товар</Наименование>
      <ЦенаЗаЕдиницу>1000.00</ЦенаЗаЕдиницу>
    </Товар>
  </Каталог>
</КоммерческаяИнформация>
EOF

# Скопировать в директорию обмена
cp /tmp/test.xml ~/onesimus/onesimus/media/1c_exchange/import0_1.xml

# Попробовать обработать через shell
python manage.py shell
```

В shell:
```python
from catalog.commerceml_views import process_commerceml_file
import os

file_path = os.path.join('media', '1c_exchange', 'import0_1.xml')
if os.path.exists(file_path):
    result = process_commerceml_file(file_path, 'import0_1.xml', None)
    print(f"Результат: {result}")
else:
    print("Файл не найден")
```

## Возможные проблемы

### Проблема 1: Файлы не загружаются (handle_file не вызывается)

**Причины:**
- 1С не доходит до этапа загрузки файлов
- Ошибка авторизации на этапе checkauth или init
- Неправильный URL в настройках 1С

**Решение:**
- Проверьте логи 1С (если доступны)
- Проверьте, что все этапы обмена проходят успешно
- Убедитесь, что URL правильный: `http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth`

### Проблема 2: Файлы загружаются, но не обрабатываются (handle_import не вызывается)

**Причины:**
- 1С не переходит к этапу import
- Файл не найден при обработке
- Ошибка на этапе import

**Решение:**
- Проверьте, что файлы действительно сохраняются (шаг 2)
- Проверьте логи Django на ошибки

### Проблема 3: Файлы обрабатываются, но товары не создаются

**Причины:**
- Неправильная структура XML
- Товары не найдены в файле
- Ошибки валидации

**Решение:**
- Проверьте структуру XML файла
- Проверьте логи синхронизации на ошибки

## Следующие шаги

1. Выполните обмен в 1С
2. Сразу после обмена проверьте директорию обмена
3. Проверьте логи синхронизации
4. Если файлы есть, но логов нет - проверьте обработку файла вручную
