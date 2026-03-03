# Исправление стилей при DEBUG=False без nginx

## Проблема
- `DEBUG = False` на сервере
- Nginx не настроен (нет `.nginx/onesimus25.ru.conf`)
- Картинки передаются (Django view работает)
- Но CSS и JS не передаются (404 или неправильный MIME тип)

## Что было исправлено
Исправлены синтаксические ошибки в функции `serve_static_file` в `config/urls.py` - были неправильные отступы, из-за которых код не работал для CSS/JS.

## Что нужно сделать на сервере

### Шаг 1: Загрузите исправленный код

```bash
cd ~/onesimus/onesimus
git pull origin main
```

### Шаг 2: Убедитесь, что файлы существуют

```bash
# Проверьте CSS
ls -la staticfiles/css/style.css
ls -la staticfiles/css/cart.css

# Проверьте JS
ls -la staticfiles/js/main.js

# Если файлов нет - соберите статику
python manage.py collectstatic --noinput
```

### Шаг 3: Перезапустите приложение

```bash
touch tmp/restart.txt
```

### Шаг 4: Проверьте логи Django

```bash
# Смотрите логи в реальном времени
tail -f logs/django.log | grep -i "static"

# Или последние записи
tail -100 logs/django.log | grep -i "static"
```

**Вы должны видеть сообщения:**
```
INFO === STATIC FILE REQUEST: /static/css/style.css ===
INFO Serving static file: path=css/style.css, file_path=...
INFO Successfully serving file: ... (Content-Type: text/css; charset=utf-8)
```

**Если этих сообщений НЕТ** - Django view не вызывается. Возможно, запросы перехватываются до Django.

**Если видите сообщения, но файл не найден** - проверьте путь:
```
INFO Serving static file: path=css/style.css, file_path=/path/to/file, exists=False
```

### Шаг 5: Проверьте через curl

```bash
# Проверьте CSS
curl -I https://onesimus25.ru/static/css/style.css

# Должно быть:
# HTTP/2 200
# Content-Type: text/css; charset=utf-8

# Если видите 404 - проверьте логи (Шаг 4)
```

### Шаг 6: Если view не вызывается

Если в логах нет сообщений `=== STATIC FILE REQUEST ===`, значит запросы не доходят до Django view.

**Возможные причины:**
1. Nginx перехватывает запросы (даже без конфигурации)
2. Passenger перехватывает запросы
3. URL паттерн не срабатывает

**Решение: Проверьте порядок URL паттернов**

Убедитесь, что паттерн для статики в начале `urlpatterns`. В исправленном коде это уже сделано.

### Шаг 7: Если файлы не находятся

Если в логах видно `exists=False`, проверьте путь:

```bash
# Узнайте реальный путь к staticfiles
realpath staticfiles

# Проверьте, что файлы там
ls -la $(realpath staticfiles)/css/style.css
```

Убедитесь, что `STATIC_ROOT` в `settings.py` указывает на правильную директорию.

## Альтернативное решение: Настройте nginx

Если Django view не работает, можно настроить nginx (даже если файла `.nginx/onesimus25.ru.conf` нет, его можно создать):

```bash
cd ~/onesimus/onesimus

# 1. Создайте директорию
mkdir -p .nginx

# 2. Узнайте путь к staticfiles
STATIC_PATH=$(realpath staticfiles)
echo "Путь к staticfiles: $STATIC_PATH"

# 3. Создайте конфигурацию
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

location /media/ {
    alias $(realpath media)/;
    expires 7d;
    add_header Cache-Control "public";
    access_log off;
}
EOF

# 4. Создайте для www (если используется)
cp .nginx/onesimus25.ru.conf .nginx/www.onesimus25.ru.conf

# 5. Установите права
chmod 644 .nginx/onesimus25.ru.conf
chmod 644 .nginx/www.onesimus25.ru.conf

# 6. Перезапустите
touch tmp/restart.txt

# 7. Подождите 1-2 минуты и проверьте
curl -I https://onesimus25.ru/static/css/style.css
```

## После исправления

1. Очистите кеш браузера (Ctrl+Shift+R)
2. Откройте консоль разработчика (F12) → Network
3. Обновите страницу
4. Проверьте запросы к CSS/JS - должен быть `200 OK` и правильный `Content-Type`

## Диагностика

Если проблема сохраняется, выполните на сервере:

```bash
cd ~/onesimus/onesimus

# 1. Проверьте DEBUG
grep "^DEBUG" config/settings.py

# 2. Проверьте STATIC_ROOT
grep "STATIC_ROOT" config/settings.py

# 3. Проверьте файлы
ls -la staticfiles/css/style.css staticfiles/js/main.js

# 4. Проверьте логи
tail -50 logs/django.log | grep -i "static"

# 5. Проверьте через curl
curl -v https://onesimus25.ru/static/css/style.css 2>&1 | head -30
```

Пришлите результаты этих команд, если проблема не решится.
