#!/bin/bash
# Скрипт для настройки nginx для статики на Beget

cd ~/onesimus/onesimus

# Создаем директорию .nginx если её нет
mkdir -p .nginx

# Получаем абсолютный путь к staticfiles
STATIC_PATH=$(realpath staticfiles)
MEDIA_PATH=$(realpath media)

echo "Путь к staticfiles: $STATIC_PATH"
echo "Путь к media: $MEDIA_PATH"

# Создаем конфигурацию для домена без www
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
    alias $MEDIA_PATH/;
    expires 7d;
    add_header Cache-Control "public";
    access_log off;
}
EOF

# Создаем конфигурацию для домена с www
cp .nginx/onesimus25.ru.conf .nginx/www.onesimus25.ru.conf

# Устанавливаем права
chmod 644 .nginx/onesimus25.ru.conf
chmod 644 .nginx/www.onesimus25.ru.conf

echo ""
echo "Конфигурация nginx создана!"
echo ""
echo "Файлы:"
echo "  .nginx/onesimus25.ru.conf"
echo "  .nginx/www.onesimus25.ru.conf"
echo ""
echo "Содержимое:"
cat .nginx/onesimus25.ru.conf
echo ""
echo "Теперь подождите 1-2 минуты, пока Beget применит изменения,"
echo "или перезапустите приложение: touch tmp/restart.txt"
echo ""
echo "Проверьте:"
echo "  curl -I https://onesimus25.ru/static/css/style.css"
