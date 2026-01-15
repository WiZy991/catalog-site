# Исправление проблем на продакшене

## Проблемы:
1. Изображения акций не отображаются (показывается иконка сломанного изображения)
2. Корзина не квадратная
3. Картинки в каталоге не круглые

## Решение:

### 1. Обновите STATIC_VERSION на сервере:

```bash
# Отредактируйте config/settings.py
sed -i "s/STATIC_VERSION = '.*'/STATIC_VERSION = '1.2'/" config/settings.py

# Или вручную откройте файл и измените:
# STATIC_VERSION = '1.2'
```

### 2. Проверьте, что CSS файлы обновились:

```bash
# Проверьте наличие изменений в файлах
grep -n "border-radius: 50%" static/css/style.css
grep -n "aspect-ratio" static/css/style.css
grep -n "!important" static/css/style.css | head -10

# Если изменений нет, файлы не обновились через git pull
# Проверьте статус git:
git status
git pull
```

### 3. Проверьте настройки MEDIA_URL для изображений акций:

```bash
# Проверьте, что MEDIA_URL настроен правильно
grep -A 2 "MEDIA_URL" config/settings.py

# Проверьте, что медиа-файлы доступны
ls -la media/promotions/

# Если директории нет, создайте её:
mkdir -p media/promotions
chmod 755 media/promotions
```

### 4. Проверьте конфигурацию веб-сервера (nginx/apache):

Убедитесь, что веб-сервер правильно обслуживает:
- `/static/` - для статических файлов (CSS, JS)
- `/media/` - для медиа-файлов (изображения акций, товаров)

Пример для nginx:
```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/static/;
}

location /media/ {
    alias /home/o/onesim8n/onesimus/onesimus/media/;
}
```

### 5. Перезапустите приложение:

```bash
# Для Passenger:
touch tmp/restart.txt

# Или перезапустите сервер
```

### 6. Очистите кеш браузера:

- Нажмите Ctrl+Shift+R (жесткая перезагрузка)
- Или откройте в режиме инкогнито
- Или очистите кеш через настройки браузера

### 7. Проверьте права доступа к медиа-файлам:

```bash
# Убедитесь, что веб-сервер может читать медиа-файлы
chmod -R 755 media/
chown -R onesim8n:newcustomers media/
```

### 8. Проверьте URL изображения акции в браузере:

Откройте инструменты разработчика (F12) → Network → найдите запрос к изображению акции.
Проверьте:
- Правильный ли URL (должен быть `/media/promotions/...`)
- Какой статус ответа (200 OK или ошибка 404?)
- Если 404 - проблема с настройками веб-сервера для медиа-файлов
