# Отладка запросов от 1С

## Проблема
Файлы не загружаются, логов нет - значит запросы не доходят до Django или не обрабатываются.

## Проверка запросов

### 1. Проверка логов веб-сервера (nginx)

```bash
# Проверить логи nginx (если доступны)
tail -100 /var/log/nginx/access.log | grep "cml/exchange"
tail -100 /var/log/nginx/error.log | grep "cml/exchange"
```

### 2. Проверка, что логирование Django работает

```bash
cd ~/onesimus/onesimus

# Проверить, что файл логов создается
ls -lah logs/

# Если файла нет, создать директорию
mkdir -p logs
chmod 755 logs

# Проверить права на запись
touch logs/test.log && rm logs/test.log && echo "Права OK" || echo "Нет прав на запись"
```

### 3. Тестовый запрос для проверки

Выполните обмен в 1С, и сразу после этого:

```bash
# Проверить последние запросы в логах Django
tail -50 logs/django.log 2>/dev/null || echo "Файл логов не создан"

# Проверить все логи (если есть)
find logs/ -name "*.log" -type f -exec tail -20 {} \;
```

### 4. Проверка через Python (в реальном времени)

```bash
python manage.py shell
```

```python
import logging
from catalog.commerceml_views import logger

# Проверить уровень логирования
print(f"Уровень логирования: {logger.level}")
print(f"Обработчики: {[h.__class__.__name__ for h in logger.handlers]}")

# Попробовать записать тестовое сообщение
logger.info("Тестовое сообщение для проверки логирования")
```

### 5. Проверка запросов через middleware

Можно временно добавить middleware для логирования всех запросов к /cml/exchange/:

```python
# В config/settings.py добавить в MIDDLEWARE
MIDDLEWARE = [
    # ... существующие middleware ...
    'django.middleware.common.CommonMiddleware',
    # Добавить кастомный middleware для логирования
]
```

### 6. Проверка через curl (имитация запроса от 1С)

```bash
# Тест checkauth
curl -v -u "admin:password" "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth"

# Если получили cookie, используйте его для следующих запросов
# Тест init
curl -v -b "1c_exchange_session=COOKIE_VALUE" "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=init"

# Тест file (загрузка файла)
echo '<?xml version="1.0"?><test>data</test>' | curl -v -X POST -b "1c_exchange_session=COOKIE_VALUE" --data-binary @- "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=file&filename=test.xml"
```

## Возможные проблемы

### Проблема 1: Запросы не доходят до Django

**Причины:**
- Nginx не проксирует запросы к Django
- Неправильная конфигурация Passenger
- Ошибка на уровне веб-сервера

**Решение:**
- Проверьте логи nginx
- Проверьте конфигурацию Passenger
- Проверьте, что URL правильный

### Проблема 2: Запросы доходят, но не обрабатываются

**Причины:**
- Ошибка авторизации (checkauth не проходит)
- Ошибка сессии (cookie не сохраняется)
- Ошибка в коде обработки

**Решение:**
- Проверьте логи Django на ошибки
- Проверьте, что авторизация работает
- Проверьте, что сессия сохраняется

### Проблема 3: Файлы загружаются, но не сохраняются

**Причины:**
- Нет прав на запись в директорию
- Ошибка при сохранении файла
- Файл сохраняется в другое место

**Решение:**
- Проверьте права на директорию
- Проверьте логи на ошибки сохранения
- Проверьте, что путь правильный

## Быстрая диагностика

Выполните обмен в 1С и сразу после этого:

```bash
# 1. Проверить файлы
ls -lah media/1c_exchange/

# 2. Проверить логи Django
tail -100 logs/django.log 2>/dev/null

# 3. Проверить логи синхронизации
python manage.py shell -c "from catalog.models import SyncLog; print(f'Логов: {SyncLog.objects.count()}')"
```

Если ничего не изменилось - значит запросы не доходят до Django.
