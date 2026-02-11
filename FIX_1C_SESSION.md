# Исправление проблемы с сессией 1С

## Проблема
1С подключается (checkauth работает), но следующие запросы не доходят до Django.

## Возможные причины

### 1. Проблема с кешем Django

Если кеш не настроен или не работает, сессия не сохраняется, и следующие запросы отклоняются.

**Проверка:**
```bash
python manage.py shell
```

```python
from django.core.cache import cache

# Проверить, работает ли кеш
try:
    cache.set('test_key', 'test_value', 60)
    value = cache.get('test_key')
    print(f"Кеш работает: {value == 'test_value'}")
except Exception as e:
    print(f"Ошибка кеша: {e}")
```

**Решение:**
Если кеш не работает, нужно настроить его в `settings.py`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

### 2. Проблема с cookie

1С может не передавать cookie в следующих запросах.

**Проверка:**
- В логах должно быть видно, передается ли cookie
- Проверить настройки 1С - должна быть поддержка cookie

### 3. Альтернативное решение - использовать сессию Django вместо кеша

Можно сохранять сессию в базе данных или использовать встроенные сессии Django.

## Временное решение - отключить проверку cookie для теста

Можно временно отключить проверку cookie, чтобы проверить, доходят ли запросы:

```python
def check_session_cookie(request):
    """Проверка Cookie сессии."""
    # ВРЕМЕННО: для отладки всегда возвращаем True
    logger.warning("Проверка cookie (ВРЕМЕННО ОТКЛЮЧЕНА ДЛЯ ОТЛАДКИ)")
    return True  # ВРЕМЕННО
    
    # Оригинальный код:
    # cookie_name = '1c_exchange_session'
    # cookie_value = request.COOKIES.get(cookie_name)
    # ...
```

⚠️ **Внимание:** Это только для отладки! После проверки нужно вернуть оригинальный код.

## Проверка всех запросов

Можно добавить middleware для логирования ВСЕХ запросов к /cml/exchange/:

```python
# В catalog/middleware.py
import logging

logger = logging.getLogger(__name__)

class CommerceMLLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'cml/exchange' in request.path:
            logger.info(f"MIDDLEWARE: {request.method} {request.path}")
            logger.info(f"  GET: {dict(request.GET)}")
            logger.info(f"  Cookies: {dict(request.COOKIES)}")
            logger.info(f"  Headers: Authorization={bool(request.META.get('HTTP_AUTHORIZATION'))}")
        response = self.get_response(request)
        return response
```

И добавить в `settings.py`:
```python
MIDDLEWARE = [
    # ...
    'catalog.middleware.CommerceMLLoggingMiddleware',
    # ...
]
```

## Быстрая проверка

1. Проверьте кеш Django
2. Проверьте логи веб-сервера (nginx) на наличие запросов к /cml/exchange/
3. Временно отключите проверку cookie для теста
4. Добавьте middleware для логирования всех запросов
