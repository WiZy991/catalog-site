# Диагностика проблемы с MIME типом text/html для CSS/JS

## Проблема
CSS и JS файлы возвращаются с MIME типом `text/html` вместо правильных типов, что приводит к ошибкам:
- "Refused to apply style... because its MIME type ('text/html') is not a supported stylesheet MIME type"
- "Refused to execute script... because its MIME type ('text/html') is not executable"

## Причины проблемы

Когда файл возвращается с MIME типом `text/html`, это означает, что вместо самого файла возвращается HTML страница. Это может происходить по нескольким причинам:

1. **Nginx перехватывает запросы и возвращает HTML страницу ошибки** (если файл не найден)
2. **Django view не вызывается**, и запрос обрабатывается другим маршрутом, который возвращает HTML
3. **Файлы не существуют** в `staticfiles/`, и Django возвращает HTML страницу 404

## Диагностика на сервере

### Шаг 1: Проверьте, что файлы существуют

```bash
cd ~/onesimus/onesimus

# Проверьте CSS файлы
ls -la staticfiles/css/style.css
ls -la staticfiles/css/cart.css

# Проверьте JS файлы
ls -la staticfiles/js/main.js

# Если файлов нет, соберите статику
python manage.py collectstatic --noinput
```

### Шаг 2: Проверьте логи Django

```bash
# Смотрите логи в реальном времени
tail -f logs/django.log | grep -i "static"

# Или проверьте последние записи
tail -100 logs/django.log | grep -i "static"
```

Вы должны видеть сообщения типа:
```
INFO === STATIC FILE REQUEST: /static/css/style.css ===
INFO Serving static file: path=css/style.css, file_path=...
INFO Successfully serving file: ... (Content-Type: text/css; charset=utf-8)
```

**Если этих сообщений НЕТ** - Django view не вызывается, проблема в nginx или порядке URL паттернов.

### Шаг 3: Проверьте настройки nginx

```bash
# Проверьте конфигурацию nginx
cat .nginx/onesimus25.ru.conf
```

**Проблема может быть в том, что nginx настроен так:**

```nginx
# НЕПРАВИЛЬНО - nginx пытается обслужить файлы, но не находит их
# и возвращает HTML страницу ошибки
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
}
```

**Если nginx не настроен правильно, он может:**
1. Перехватывать запросы к `/static/`
2. Не находить файлы (неправильный путь)
3. Возвращать HTML страницу ошибки с MIME типом `text/html`

### Шаг 4: Проверьте через curl

```bash
# Проверьте, что возвращает сервер для CSS файла
curl -I https://onesimus25.ru/static/css/style.css

# Должно быть:
# HTTP/2 200
# Content-Type: text/css; charset=utf-8

# Если видите:
# HTTP/2 404
# Content-Type: text/html; charset=utf-8
# Это означает, что файл не найден и возвращается HTML страница 404
```

### Шаг 5: Проверьте полный ответ

```bash
# Посмотрите, что именно возвращается
curl https://onesimus25.ru/static/css/style.css | head -20

# Если видите HTML (например, "<!DOCTYPE html>" или "<html>") - 
# это означает, что возвращается HTML страница вместо CSS файла
```

## Решения

### Решение 1: Отключите nginx для статики (если он неправильно настроен)

Если nginx настроен неправильно и возвращает HTML вместо файлов, можно временно отключить его для статики:

1. Удалите или закомментируйте блок `location /static/` в `.nginx/onesimus25.ru.conf`
2. Перезапустите nginx (или подождите, пока Beget применит изменения)
3. Django view будет обрабатывать запросы к статике

### Решение 2: Правильно настройте nginx

Если хотите использовать nginx для статики (рекомендуется для производительности), настройте его правильно:

```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
    
    # Явно указываем типы для CSS и JS
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

**ВАЖНО**: Убедитесь, что путь правильный и файлы существуют по этому пути!

### Решение 3: Используйте Django view (если nginx не работает)

Если nginx не настроен или работает неправильно, Django view должен обрабатывать запросы. Убедитесь, что:

1. Паттерн для статики находится в начале `urlpatterns` (уже исправлено)
2. `DEBUG = False` в `settings.py`
3. Файлы существуют в `staticfiles/`

### Решение 4: Временно включите DEBUG=True для тестирования

Для диагностики можно временно установить `DEBUG = True`:

```bash
# На сервере
sed -i "s/DEBUG = False/DEBUG = True/" config/settings.py
# или
sed -i "s/DEBUG = True/DEBUG = False/" config/settings.py  # если уже True

touch tmp/restart.txt
```

При `DEBUG=True` Django использует стандартный механизм `staticfiles_urlpatterns()`, который должен работать правильно.

## Проверка после исправлений

1. **Очистите кеш браузера** (Ctrl+Shift+R)
2. **Откройте консоль разработчика** (F12) → Network
3. **Обновите страницу**
4. **Проверьте запросы к CSS/JS**:
   - Status: `200 OK`
   - Content-Type: `text/css` или `application/javascript`
   - Response: должен быть виден код CSS/JS, а не HTML

## Важные замечания

- **MIME тип критически важен** - браузер проверяет MIME тип перед применением стилей/выполнением скриптов
- **Если возвращается HTML** - это означает, что либо файл не найден (404), либо запрос обрабатывается неправильно
- **Nginx имеет приоритет** - если nginx настроен для `/static/`, он обрабатывает запросы ДО Django
- **Порядок URL паттернов важен** - паттерн для статики должен быть первым в списке

## Быстрая проверка

Выполните на сервере:

```bash
cd ~/onesimus/onesimus

# 1. Проверьте файлы
ls -la staticfiles/css/style.css staticfiles/js/main.js

# 2. Если файлов нет - соберите
python manage.py collectstatic --noinput

# 3. Проверьте через curl
curl -I https://onesimus25.ru/static/css/style.css

# 4. Проверьте логи
tail -50 logs/django.log | grep -i "static"
```

Если после всех проверок проблема сохраняется, проверьте настройки nginx - скорее всего проблема там.
