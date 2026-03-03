# Исправление проблемы с CSS и JS файлами

## Проблема
Картинки загружаются, но стили (CSS) и JavaScript не работают.

## Что было исправлено

1. **Улучшена функция `serve_static_file`** в `config/urls.py`:
   - Правильная обработка query string параметров (`?v=2.7`)
   - Правильное определение MIME-типов для CSS и JS
   - Добавлено подробное логирование для диагностики

2. **Добавлен логгер** для `config.urls` в `settings.py` для отслеживания запросов к статике

## Что нужно сделать на сервере

### Шаг 1: Загрузите изменения

```bash
cd ~/onesimus/onesimus
git pull origin main
```

### Шаг 2: Проверьте, что CSS и JS файлы существуют

```bash
# Проверьте наличие файлов
ls -la staticfiles/css/style.css
ls -la staticfiles/css/cart.css
ls -la staticfiles/js/main.js

# Проверьте права доступа
chmod 644 staticfiles/css/*.css
chmod 644 staticfiles/js/*.js
```

### Шаг 3: Если файлов нет, соберите статику

```bash
python manage.py collectstatic --noinput
```

### Шаг 4: Проверьте настройки nginx

Если используется nginx, проверьте файл `.nginx/onesimus25.ru.conf`:

```bash
cat .nginx/onesimus25.ru.conf
```

Должно быть:

```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
}
```

**ВАЖНО**: Если nginx настроен, но CSS/JS не работают, возможно nginx возвращает неправильный Content-Type. 

Попробуйте добавить в конфигурацию nginx:

```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
    
    # Явно указываем типы для CSS и JS
    location ~* \.css$ {
        add_header Content-Type text/css;
    }
    location ~* \.js$ {
        add_header Content-Type application/javascript;
    }
}
```

Или более простой вариант:

```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
    default_type application/octet-stream;
    types {
        text/css css;
        application/javascript js;
        image/png png;
        image/jpeg jpg jpeg;
        image/svg+xml svg;
        image/webp webp;
    }
}
```

### Шаг 5: Если nginx не настроен или не работает

Django view должен работать автоматически. Проверьте логи:

```bash
tail -f logs/django.log | grep "static"
```

Вы должны видеть сообщения типа:
```
INFO Serving static file: path=css/style.css, file_path=...
INFO Successfully serving file: ... (Content-Type: text/css; charset=utf-8)
```

### Шаг 6: Перезапустите приложение

```bash
touch tmp/restart.txt
```

### Шаг 7: Проверьте в браузере

1. Откройте сайт: https://onesimus25.ru/
2. Откройте консоль разработчика (F12)
3. Перейдите на вкладку "Network" (Сеть)
4. Обновите страницу (Ctrl+R)
5. Найдите запросы к `/static/css/style.css` и `/static/js/main.js`
6. Проверьте:
   - **Status**: должен быть `200 OK`
   - **Content-Type**: 
     - Для CSS: `text/css` или `text/css; charset=utf-8`
     - Для JS: `application/javascript` или `application/javascript; charset=utf-8`
   - **Response**: должен быть виден код CSS/JS

### Шаг 8: Если файлы возвращают 404

Проверьте URL в браузере. Должно быть:
- `https://onesimus25.ru/static/css/style.css?v=2.7`
- `https://onesimus25.ru/static/js/main.js?v=2.7`

Если видите 404, проверьте:
1. Существуют ли файлы в `staticfiles/`
2. Правильно ли настроен nginx (если используется)
3. Правильно ли работает Django view (проверьте логи)

### Шаг 9: Если файлы возвращают неправильный Content-Type

Если Content-Type не `text/css` или `application/javascript`, то браузер не будет применять стили/выполнять скрипты.

**Решение**: 
- Если используется nginx - обновите конфигурацию (см. Шаг 4)
- Если используется Django view - он должен автоматически определять правильный тип

### Шаг 10: Очистите кеш браузера

После исправлений:
1. Очистите кеш браузера (Ctrl+Shift+Delete)
2. Или откройте сайт в режиме инкогнито
3. Или используйте жесткую перезагрузку (Ctrl+Shift+R)

## Диагностика через curl

Проверьте доступность файлов напрямую:

```bash
# Проверьте CSS
curl -I https://onesimus25.ru/static/css/style.css

# Должен вернуть:
# HTTP/2 200
# Content-Type: text/css; charset=utf-8

# Проверьте JS
curl -I https://onesimus25.ru/static/js/main.js

# Должен вернуть:
# HTTP/2 200
# Content-Type: application/javascript; charset=utf-8
```

Если видите `HTTP/2 404` или другой статус - проблема в настройке nginx или Django.

## Если ничего не помогает

1. Временно установите `DEBUG = True` в `settings.py` на сервере
2. Перезапустите приложение
3. Проверьте, работает ли статика
4. Если работает - проблема в настройке nginx или в Django view для DEBUG=False
5. Если не работает - проблема в файлах или путях

## Важные замечания

- **Query string параметры** (`?v=2.7`) используются только для кеширования браузера
- Django view автоматически игнорирует query string при поиске файла
- Nginx также должен игнорировать query string при поиске файла
- **Content-Type критически важен** - без правильного типа браузер не применит стили/не выполнит скрипты
