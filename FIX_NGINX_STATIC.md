# Исправление проблемы со статическими файлами

## Проблема
Nginx возвращает 404 для `/static/`, потому что он не настроен для раздачи статики или не передает запросы в Django.

## Решение

### Вариант 1: Настроить Nginx для раздачи статики напрямую (РЕКОМЕНДУЕТСЯ)

На сервере найдите конфигурацию Nginx для вашего сайта:

```bash
# Найдите конфигурацию Nginx
cat /etc/nginx/sites-enabled/*onesimus* 2>/dev/null || \
cat /etc/nginx/conf.d/*onesimus* 2>/dev/null || \
cat ~/nginx.conf 2>/dev/null || \
cat ~/.nginx/onesimus* 2>/dev/null
```

Добавьте или обновите блок для статики:

```nginx
server {
    # ... другие настройки ...
    
    # Статические файлы
    location /static/ {
        alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Медиа-файлы
    location /media/ {
        alias /home/o/onesim8n/onesimus/onesimus/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Все остальные запросы передаем в Django
    location / {
        # ... настройки Passenger/Django ...
    }
}
```

После изменения конфигурации Nginx:

```bash
# Проверьте конфигурацию
sudo nginx -t

# Перезагрузите Nginx
sudo systemctl reload nginx
# или
sudo service nginx reload
```

### Вариант 2: Если нет доступа к Nginx, используйте Django для раздачи статики

Убедитесь, что в `config/urls.py` правильно настроена раздача статики (уже сделано).

Проверьте, что Django может раздать статику:

```bash
# Проверьте, что файлы существуют
ls -la staticfiles/css/style.css
ls -la static/css/style.css

# Проверьте права доступа
chmod -R 755 staticfiles/
chmod -R 755 static/

# Перезапустите Django
touch tmp/restart.txt
```

### Вариант 3: Временное решение - изменить STATIC_URL

Если Nginx настроен на раздачу статики из другого пути, можно временно изменить `STATIC_URL` в `config/settings.py`:

```python
STATIC_URL = '/assets/'  # Вместо '/static/'
```

Но это потребует изменения всех шаблонов, поэтому не рекомендуется.

## Проверка

После настройки проверьте:

```bash
# Проверьте через curl
curl -I https://onesimus25.ru/static/css/style.css

# Должен вернуть:
# HTTP/2 200
# Content-Type: text/css
```

Если возвращается 404, значит Nginx все еще перехватывает запросы. Проверьте конфигурацию Nginx еще раз.
