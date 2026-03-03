# Решение проблемы со статикой на Beget

## Проблема
Nginx блокирует запросы к `/static/` и возвращает 404 до того, как они доходят до Django.

## Решение

### Вариант 1: Настроить Nginx через панель Beget (РЕКОМЕНДУЕТСЯ)

1. Войдите в панель управления Beget: https://beget.com/ru/panel
2. Найдите раздел **"Сайты"** или **"Домены"**
3. Выберите домен `onesimus25.ru`
4. Найдите раздел **"Настройка Nginx"** или **"Дополнительные настройки"**
5. Добавьте следующую конфигурацию:

```nginx
location /static/ {
    proxy_pass http://127.0.0.1:YOUR_PASSENGER_PORT;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Или если Nginx должен раздавать статику напрямую:

```nginx
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

### Вариант 2: Обратиться в поддержку Beget

Напишите в поддержку Beget с запросом:

> Здравствуйте! У меня проблема с раздачей статических файлов для домена onesimus25.ru. 
> Nginx блокирует запросы к `/static/` и возвращает 404. 
> Нужно настроить Nginx так, чтобы он либо раздавал статику из `/home/o/onesim8n/onesimus/onesimus/staticfiles/`, 
> либо передавал запросы `/static/` в Django/Passenger.
> 
> Путь к статике: `/home/o/onesim8n/onesimus/onesimus/staticfiles/`
> Домен: onesimus25.ru

### Вариант 3: Временное решение - вернуть DEBUG=True

Если срочно нужно, чтобы сайт работал:

```bash
sed -i "s/DEBUG = False/DEBUG = True/" config/settings.py
touch tmp/restart.txt
```

Но это не рекомендуется для production.

### Вариант 4: Проверить, работает ли старый домен

Проверьте, работает ли статика для старого домена:

```bash
curl -I https://onesim8n.beget.tech/static/css/style.css
```

Если работает - значит проблема только в настройке нового домена `onesimus25.ru` в Nginx.

## Проверка после настройки

```bash
curl -I https://onesimus25.ru/static/css/style.css
```

Должен вернуться `HTTP/2 200` и `Content-Type: text/css`.
