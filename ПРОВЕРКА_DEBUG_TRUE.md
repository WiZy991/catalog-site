# Проверка с DEBUG=True

## Шаг 1: Временно включите DEBUG=True

```bash
cd ~/onesimus/onesimus

# Сохраните текущее значение DEBUG
grep "^DEBUG" config/settings.py

# Временно включите DEBUG
sed -i "s/DEBUG = False/DEBUG = True/" config/settings.py

# Перезапустите
touch tmp/restart.txt

# Подождите 10 секунд
sleep 10

# Проверьте
curl -I https://onesimus25.ru/static/css/style.css
```

## Что проверить:

1. **Если заработало** (HTTP 200, Content-Type: text/css):
   - Проблема в кастомном view при `DEBUG=False`
   - Нужно исправить view или использовать стандартный механизм Django

2. **Если не заработало** (всё еще 404):
   - Проблема в nginx/Passenger, который перехватывает запросы
   - Нужно настроить nginx или найти, почему запросы не доходят до Django

## Шаг 2: Проверьте логи

```bash
# Смотрите логи в реальном времени
tail -f logs/django.log | grep -i "static"

# В другом терминале сделайте запрос
curl https://onesimus25.ru/static/css/style.css > /dev/null
```

При `DEBUG=True` Django использует `staticfiles_urlpatterns()`, который должен работать автоматически.

## Шаг 3: Если заработало с DEBUG=True

Значит проблема в кастомном view. Проверьте:

```bash
# Верните DEBUG=False
sed -i "s/DEBUG = True/DEBUG = False/" config/settings.py

# Убедитесь, что код загружен
git pull origin main

# Проверьте, что паттерн для статики в начале urlpatterns
grep -A 10 "if settings.DEBUG:" config/urls.py

# Перезапустите
touch tmp/restart.txt
```

## Шаг 4: Если не заработало даже с DEBUG=True

Значит проблема в конфигурации веб-сервера (nginx/Passenger). В этом случае нужно настроить nginx:

```bash
mkdir -p .nginx

STATIC_PATH=$(realpath staticfiles)
cat > .nginx/onesimus25.ru.conf << EOF
location /static/ {
    alias $STATIC_PATH/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
    
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
EOF

cp .nginx/onesimus25.ru.conf .nginx/www.onesimus25.ru.conf
touch tmp/restart.txt
```
