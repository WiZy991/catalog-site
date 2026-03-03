# Настройка nginx для статики на Beget

## Проблема
Файлы существуют, но возвращается 404. Nginx не настроен для статики, и Django view не вызывается.

## Решение: Создать конфигурацию nginx

### Шаг 1: Создайте директорию .nginx (если её нет)

```bash
cd ~/onesimus/onesimus
mkdir -p .nginx
```

### Шаг 2: Создайте файл конфигурации для домена

```bash
# Для домена без www
nano .nginx/onesimus25.ru.conf

# Для домена с www (если используется)
nano .nginx/www.onesimus25.ru.conf
```

### Шаг 3: Добавьте конфигурацию для статики

Скопируйте в файл `.nginx/onesimus25.ru.conf`:

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
        font/woff2 woff2;
        font/woff woff;
        application/font-woff woff;
    }
    default_type application/octet-stream;
}

location /media/ {
    alias /home/o/onesim8n/onesimus/onesimus/media/;
    expires 7d;
    add_header Cache-Control "public";
    access_log off;
}
```

**ВАЖНО**: Убедитесь, что путь правильный! Проверьте:
```bash
ls -la /home/o/onesim8n/onesimus/onesimus/staticfiles/css/style.css
```

Если путь другой, исправьте в конфигурации.

### Шаг 4: Создайте такой же файл для www (если используется)

```bash
cp .nginx/onesimus25.ru.conf .nginx/www.onesimus25.ru.conf
```

### Шаг 5: Проверьте права доступа

```bash
chmod 644 .nginx/onesimus25.ru.conf
chmod 644 .nginx/www.onesimus25.ru.conf
```

### Шаг 6: Подождите применения изменений

Beget автоматически применяет изменения из `.nginx/` в течение 1-2 минут.

Или перезапустите приложение:
```bash
touch tmp/restart.txt
```

### Шаг 7: Проверьте

```bash
# Проверьте CSS
curl -I https://onesimus25.ru/static/css/style.css

# Должно быть:
# HTTP/2 200
# Content-Type: text/css

# Проверьте JS
curl -I https://onesimus25.ru/static/js/main.js

# Должно быть:
# HTTP/2 200
# Content-Type: application/javascript
```

## Альтернатива: Если nginx не работает

Если после настройки nginx все еще не работает, можно использовать Django view:

1. Убедитесь, что `DEBUG = False` на сервере
2. Убедитесь, что паттерн для статики в начале `urlpatterns` (уже исправлено)
3. Проверьте логи Django:
   ```bash
   tail -f logs/django.log | grep -i "static"
   ```

## Проверка пути к файлам

```bash
# Узнайте полный путь к проекту
pwd

# Проверьте, что файлы существуют
ls -la staticfiles/css/style.css
ls -la staticfiles/js/main.js

# Узнайте абсолютный путь
realpath staticfiles/css/style.css
```

Используйте этот путь в конфигурации nginx.
