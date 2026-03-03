# СРОЧНОЕ ИСПРАВЛЕНИЕ: MIME тип text/html для CSS/JS

## Проблема
CSS и JS файлы возвращаются с MIME типом `text/html` вместо правильных типов, из-за чего стили и скрипты не применяются.

## Что было исправлено в коде

1. ✅ Паттерн для статики перемещен в **начало** `urlpatterns` для приоритета
2. ✅ Улучшено логирование для диагностики
3. ✅ Правильное определение MIME типов для CSS и JS

## Что нужно сделать на сервере ПРЯМО СЕЙЧАС

### Шаг 1: Загрузите изменения

```bash
cd ~/onesimus/onesimus
git pull origin main
```

### Шаг 2: Убедитесь, что файлы существуют

```bash
# Проверьте наличие файлов
ls -la staticfiles/css/style.css
ls -la staticfiles/js/main.js

# Если файлов НЕТ - соберите статику
python manage.py collectstatic --noinput
```

### Шаг 3: Проверьте настройки nginx

**ВАЖНО**: Проблема скорее всего в nginx! Он может перехватывать запросы и возвращать HTML вместо файлов.

```bash
# Проверьте конфигурацию
cat .nginx/onesimus25.ru.conf
```

**Если в конфигурации есть блок `location /static/`, но он неправильно настроен:**

**Вариант А: Временно отключите nginx для статики**

Закомментируйте или удалите блок `location /static/` в `.nginx/onesimus25.ru.conf`:

```nginx
# location /static/ {
#     alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
# }
```

Тогда Django view будет обрабатывать запросы.

**Вариант Б: Правильно настройте nginx**

Обновите `.nginx/onesimus25.ru.conf`:

```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
    
    # КРИТИЧЕСКИ ВАЖНО: Явно указываем типы для CSS и JS
    types {
        text/css css;
        application/javascript js;
        image/png png;
        image/jpeg jpg jpeg;
        image/svg+xml svg;
        image/webp webp;
    }
    default_type application/octet-stream;
}
```

**Убедитесь, что путь правильный!** Проверьте:
```bash
ls -la /home/o/onesim8n/onesimus/onesimus/staticfiles/css/style.css
```

### Шаг 4: Перезапустите приложение

```bash
touch tmp/restart.txt
```

### Шаг 5: Проверьте через curl

```bash
# Проверьте CSS
curl -I https://onesimus25.ru/static/css/style.css

# Должно быть:
# HTTP/2 200
# Content-Type: text/css; charset=utf-8

# Если видите:
# Content-Type: text/html; charset=utf-8
# Это означает, что возвращается HTML страница вместо CSS!
```

### Шаг 6: Проверьте логи Django

```bash
tail -f logs/django.log | grep -i "static"
```

Вы должны видеть:
```
INFO === STATIC FILE REQUEST: /static/css/style.css ===
INFO Serving static file: path=css/style.css...
INFO Successfully serving file: ... (Content-Type: text/css; charset=utf-8)
```

**Если этих сообщений НЕТ** - Django view не вызывается, проблема в nginx!

## Быстрое решение (если ничего не помогает)

1. **Временно отключите nginx для статики** (удалите блок `location /static/`)
2. **Убедитесь, что `DEBUG = False`** в `settings.py`
3. **Соберите статику**: `python manage.py collectstatic --noinput`
4. **Перезапустите**: `touch tmp/restart.txt`
5. **Проверьте**: `curl -I https://onesimus25.ru/static/css/style.css`

Django view должен обработать запрос и вернуть правильный MIME тип.

## После исправления

1. Очистите кеш браузера (Ctrl+Shift+R)
2. Откройте консоль разработчика (F12) → Network
3. Обновите страницу
4. Проверьте запросы к CSS/JS - должен быть `Content-Type: text/css` или `application/javascript`

## Подробная диагностика

См. файл `ДИАГНОСТИКА_MIME_TYPE.md` для подробной диагностики проблемы.
