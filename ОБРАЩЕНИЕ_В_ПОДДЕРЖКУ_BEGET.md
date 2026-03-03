# Обращение в поддержку Beget

## Текст обращения:

```
Здравствуйте!

У меня проблема с раздачей статических файлов (CSS, JS, изображения) на домене onesimus25.ru.

Проблема:
- Запросы к /static/css/style.css, /static/js/main.js возвращают 404
- Файлы существуют в директории /home/o/onesim8n/onesimus/onesimus/staticfiles/
- На старом домене onesim8n.beget.tech всё работало без дополнительных настроек

Диагностика:
- curl показывает: HTTP/2 404, content-type: text/html (179 байт - HTML страница 404)
- Запросы не доходят до Django приложения (нет логов в django.log)
- Это означает, что nginx/Passenger перехватывает запросы к /static/ и возвращает 404

Вопросы:
1. Можете ли вы настроить nginx для обслуживания статических файлов из директории /home/o/onesim8n/onesimus/onesimus/staticfiles/?
2. Или проверить, почему запросы к /static/ не доходят до Django приложения?
3. Возможно, на новом домене автоматически настроена конфигурация nginx, которая блокирует /static/?

Нужная конфигурация nginx для /static/:
location /static/ {
    alias /home/o/onesim8n/onesimus/onesimus/staticfiles/;
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

Спасибо!
```

## Альтернативный вариант (короче):

```
Здравствуйте!

На домене onesimus25.ru не работают статические файлы (CSS, JS).
Запросы к /static/ возвращают 404, хотя файлы существуют в /home/o/onesim8n/onesimus/onesimus/staticfiles/

На старом домене onesim8n.beget.tech всё работало.

Можете настроить nginx для обслуживания статики из этой директории?
Или проверить, почему запросы не доходят до Django приложения?

Спасибо!
```

## Что указать в обращении:

1. **Домен**: onesimus25.ru
2. **Путь к статике**: /home/o/onesim8n/onesimus/onesimus/staticfiles/
3. **Проблема**: 404 для /static/css/style.css, /static/js/main.js
4. **На старом домене**: работало без настроек

## Что попросить:

1. Настроить nginx для обслуживания статики
2. Или проверить конфигурацию nginx для нового домена
3. Или дать доступ к конфигурации nginx (если она заблокирована)

## После обращения:

Поддержка Beget обычно отвечает быстро и может:
- Настроить nginx за вас
- Проверить конфигурацию
- Объяснить, почему запросы не доходят до Django

Это самый простой способ решить проблему!
