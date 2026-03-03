# СРОЧНО: Настройка nginx для статики

## Проблема
Все запросы к `/static/` возвращают 404, потому что nginx/Passenger перехватывает их ДО Django и не находит файлы.

## Решение: Настроить nginx

Выполните на сервере:

```bash
cd ~/onesimus/onesimus

# 1. Создайте директорию .nginx
mkdir -p .nginx

# 2. Узнайте абсолютный путь к staticfiles
STATIC_PATH=$(realpath staticfiles)
echo "Путь к staticfiles: $STATIC_PATH"

# 3. Создайте конфигурацию для домена без www
cat > .nginx/onesimus25.ru.conf << EOF
location /static/ {
    alias $STATIC_PATH/;
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
    alias $(realpath media)/;
    expires 7d;
    add_header Cache-Control "public";
    access_log off;
}
EOF

# 4. Создайте для домена с www (если используется)
cp .nginx/onesimus25.ru.conf .nginx/www.onesimus25.ru.conf

# 5. Установите права
chmod 644 .nginx/onesimus25.ru.conf
chmod 644 .nginx/www.onesimus25.ru.conf

# 6. Проверьте содержимое
echo "=== Конфигурация для onesimus25.ru ==="
cat .nginx/onesimus25.ru.conf

# 7. Перезапустите приложение
touch tmp/restart.txt

# 8. Подождите 1-2 минуты (Beget применяет изменения автоматически)

# 9. Проверьте
echo ""
echo "Проверка через 2 минуты..."
sleep 120
curl -I https://onesimus25.ru/static/css/style.css
```

## После настройки

Проверьте:

```bash
# Проверьте CSS
curl -I https://onesimus25.ru/static/css/style.css
# Должно быть: HTTP/2 200 и Content-Type: text/css

# Проверьте JS
curl -I https://onesimus25.ru/static/js/main.js
# Должно быть: HTTP/2 200 и Content-Type: application/javascript

# Проверьте изображение
curl -I https://onesimus25.ru/static/images/logo.png
# Должно быть: HTTP/2 200 и Content-Type: image/png
```

## Если все еще 404

1. Проверьте, что путь правильный:
   ```bash
   ls -la $STATIC_PATH/css/style.css
   ```

2. Проверьте права доступа:
   ```bash
   chmod -R 755 $STATIC_PATH
   chmod -R 644 $STATIC_PATH/**/*
   ```

3. Проверьте, что файл конфигурации создан:
   ```bash
   ls -la .nginx/onesimus25.ru.conf
   cat .nginx/onesimus25.ru.conf
   ```

4. Подождите еще 2-3 минуты - Beget может применять изменения с задержкой

## Важно

После настройки nginx Django view больше не будет вызываться для статики - nginx будет обслуживать файлы напрямую, что быстрее и правильнее для продакшена.
