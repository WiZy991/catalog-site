# Исправление логирования

## Проблема
Файл логов пустой - логирование не работает.

## Решение

### 1. Проверка логирования через Python

```bash
cd ~/onesimus/onesimus
python manage.py shell
```

```python
import logging
import os
from django.conf import settings

# Проверить настройки логирования
print("LOGGING config:", settings.LOGGING)

# Проверить логгер
from catalog import commerceml_views
logger = commerceml_views.logger

print(f"\nЛоггер: {logger.name}")
print(f"Уровень: {logger.level}")
print(f"Обработчики: {[h.__class__.__name__ for h in logger.handlers]}")

# Попробовать записать
logger.info("ТЕСТ: Сообщение из shell")
logger.error("ТЕСТ: Ошибка из shell")

# Проверить файл
log_file = os.path.join(settings.BASE_DIR, 'logs', 'django.log')
print(f"\nФайл логов: {log_file}")
print(f"Существует: {os.path.exists(log_file)}")
if os.path.exists(log_file):
    print(f"Размер: {os.path.getsize(log_file)} байт")
    with open(log_file, 'r') as f:
        content = f.read()
        print(f"Содержимое ({len(content)} символов):")
        print(content[-500:] if content else "Файл пустой")
```

### 2. Проверка прав на файл

```bash
# Проверить права
ls -la logs/django.log

# Дать права на запись всем
chmod 666 logs/django.log

# Проверить владельца
ls -la logs/
```

### 3. Альтернатива - логирование в другой файл

Если текущий файл не работает, можно временно логировать в другой:

```python
# В settings.py изменить путь к логу
'filename': os.path.join(BASE_DIR, 'commerceml.log'),
```

### 4. Проверка через print (временное решение)

Можно временно добавить print для отладки:

```python
# В commerceml_views.py добавить print в начале функции
def commerceml_exchange(request):
    print(f"DEBUG: commerceml_exchange вызван: {request.GET}")
    logger.info(f"commerceml_exchange: type={exchange_type}...")
    # ...
```

Эти print будут видны в логах веб-сервера или в консоли.

### 5. Проверка через middleware

Можно добавить middleware для логирования всех запросов:

```python
# Создать catalog/middleware.py
import logging

logger = logging.getLogger(__name__)

class CommerceMLLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'cml/exchange' in request.path:
            logger.info(f"CommerceML request: {request.method} {request.path} {request.GET}")
        response = self.get_response(request)
        return response
```

И добавить в settings.py:
```python
MIDDLEWARE = [
    # ...
    'catalog.middleware.CommerceMLLoggingMiddleware',
    # ...
]
```
