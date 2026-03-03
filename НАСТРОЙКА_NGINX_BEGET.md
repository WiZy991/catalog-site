# Настройка Nginx для статических файлов на Beget

## Проблема
Конфигурация Nginx была настроена для старого домена `onesim8n.beget.tech`, а для нового домена `onesimus25.ru` её нет или она не настроена.

## Шаг 1: Найдите существующие конфигурации Nginx

В файловом менеджере Beget найдите папку `.nginx` в корне проекта:
- Путь: `/home/o/onesim8n/onesimus/onesimus/.nginx/`

Проверьте, какие файлы там есть:
- `onesim8n.beget.tech.conf` (старый домен)
- `onesimus25.ru.conf` (новый домен - может отсутствовать)
- `www.onesimus25.ru.conf` (домен с www)

## Шаг 2: Создайте или отредактируйте файл конфигурации для нового домена

**ВАЖНО:** Создайте файл `.nginx/onesimus25.ru.conf` (для домена без www) и `.nginx/www.onesimus25.ru.conf` (для домена с www).

Добавьте в оба файла одинаковую конфигурацию:

```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
}

location /media/ {
    alias /home/o/onesim8n/onesimus/onesimus/media/;
    expires 7d;
    add_header Cache-Control "public";
    access_log off;
}
```

## Шаг 3: Скопируйте конфигурацию со старого домена (если нужно)

Если в `.nginx/onesim8n.beget.tech.conf` уже есть настройки для статики, скопируйте их в новый файл.

## Шаг 4: Примените изменения

После сохранения файла Beget автоматически применит изменения (обычно в течение 1-2 минут).

Или через SSH:

```bash
# Проверьте, что файлы созданы
ls -la .nginx/*onesimus25.ru.conf

# Проверьте содержимое
cat .nginx/onesimus25.ru.conf
cat .nginx/www.onesimus25.ru.conf
```

## Шаг 5: Проверьте

```bash
curl -I https://onesimus25.ru/static/css/style.css
```

Должен вернуться `HTTP/2 200` и `Content-Type: text/css`.

## Альтернатива: Если нет доступа к .nginx

Если папка `.nginx` недоступна, можно настроить через панель управления Beget:

1. Войдите в панель управления Beget
2. Найдите раздел "Настройка сайта" или "Nginx"
3. Выберите домен `onesimus25.ru` (и `www.onesimus25.ru`)
4. Добавьте кастомную конфигурацию с блоками `location /static/` и `location /media/`

## Важно: Два домена

На Beget нужно настроить конфигурацию для **обоих** доменов:
- `onesimus25.ru` (без www)
- `www.onesimus25.ru` (с www)

Создайте два файла с одинаковым содержимым:
- `.nginx/onesimus25.ru.conf`
- `.nginx/www.onesimus25.ru.conf`

## Важно

- Путь к `staticfiles/` должен быть **абсолютным**: `/home/o/onesim8n/onesimus/onesimus/staticfiles/`
- Убедитесь, что файлы в `staticfiles/` имеют правильные права доступа (755 для папок, 644 для файлов)
