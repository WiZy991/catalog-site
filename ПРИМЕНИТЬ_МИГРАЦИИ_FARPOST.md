# Инструкция по применению миграций для Farpost на сервере

## Проблема
Ошибка: `no such table: catalog_productcharacteristic`

Это означает, что на сервере не применены миграции 0012 и 0013.

## Решение

Выполните на сервере следующие команды:

```bash
# 1. Перейдите в директорию проекта
cd /home/o/onesim8n/onesimus/onesimus

# 2. Активируйте виртуальное окружение
source venv/bin/activate

# 3. Загрузите последние изменения из репозитория
git pull origin main

# 4. Проверьте статус миграций
python manage.py showmigrations catalog

# 5. Примените все неприменённые миграции
python manage.py migrate catalog

# 6. Если есть проблемы, можно применить конкретные миграции:
python manage.py migrate catalog 0012_synclog_productcharacteristic
python manage.py migrate catalog 0013_add_farpost_auto_update_fields

# 7. Проверьте, что все миграции применены
python manage.py showmigrations catalog
```

## Что делают эти миграции

### Миграция 0012
- Создаёт таблицу `SyncLog` (логи синхронизации)
- Создаёт таблицу `ProductCharacteristic` (характеристики товаров)

### Миграция 0013
- Добавляет поле `api_key` в `FarpostAPISettings`
- Добавляет поля для автоматического обновления:
  - `auto_update_enabled`
  - `auto_update_url`
  - `auto_update_interval`
  - `last_auto_update`

## После применения миграций

1. Перезапустите приложение:
   ```bash
   touch tmp/restart.txt
   ```

2. Проверьте, что ошибка исчезла, попробовав удалить товар в админке.

## Если возникнут проблемы

Если миграция не применяется из-за конфликтов:

```bash
# Показать детальную информацию о миграциях
python manage.py migrate catalog --verbosity=2

# Если нужно откатить миграцию (осторожно!)
python manage.py migrate catalog 0011_populate_category_keywords
```
