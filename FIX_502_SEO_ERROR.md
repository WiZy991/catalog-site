# Исправление ошибки 502 после добавления SEO

## Проблема
После добавления SEO настроек появилась ошибка 502 Bad Gateway.

## Причина
Context processor `core.context_processors.seo_processor` может вызывать ошибку, если на сервере отсутствуют новые настройки из `settings.py`.

## Решение

### 1. Обновить код на сервере
Убедитесь, что файл `core/context_processors.py` обновлен с защитой от ошибок.

### 2. Проверить настройки в settings.py
Убедитесь, что на сервере в `config/settings.py` есть следующие настройки:

```python
# SEO Settings - Домены
SITE_DOMAIN = 'onesimus25.ru'
SITE_DOMAIN_WWW = 'www.onesimus25.ru'
SITE_DOMAIN_TEMP = 'onesim8n.beget.tech'

# SEO Keywords
SITE_KEYWORDS = 'автозапчасти, запчасти для автомобилей, купить автозапчасти, автозапчасти Уссурийск, доставка автозапчастей, каталог автозапчастей, запчасти Приморский край'

# Open Graph и Social Media
SITE_OG_TYPE = 'website'
SITE_TWITTER_CARD = 'summary_large_image'
SITE_TWITTER_SITE = ''

# Дополнительная информация для SEO
SITE_LOCALE = 'ru_RU'
SITE_LANGUAGE = 'ru'

# Поисковые системы - Verification коды
YANDEX_VERIFICATION = ''
GOOGLE_VERIFICATION = ''
YANDEX_METRICA_ID = ''
```

### 3. Перезапустить приложение на Beget

#### Вариант 1: Через панель управления Beget
1. Войдите в панель управления Beget
2. Перейдите в раздел "Сайты" → "Управление Python"
3. Найдите ваш сайт и нажмите "Перезапустить"

#### Вариант 2: Через SSH
```bash
# Подключитесь к серверу
ssh ваш_логин@onesim8n.beget.tech

# Перейдите в директорию проекта
cd ~/web

# Активируйте виртуальное окружение (если используется)
source venv/bin/activate

# Проверьте логи на ошибки
tail -n 50 logs/django.log

# Перезапустите приложение (способ зависит от конфигурации)
# Если используется systemd:
sudo systemctl restart ваш_сервис

# Если используется supervisor:
supervisorctl restart ваш_процесс

# Если используется screen/tmux:
# Найдите процесс и перезапустите его
```

### 4. Проверить логи
```bash
# Логи Django
tail -f logs/django.log

# Логи веб-сервера (nginx/apache)
tail -f /var/log/nginx/error.log
# или
tail -f /var/log/apache2/error.log
```

### 5. Временное отключение context processor (если ничего не помогает)
Если проблема сохраняется, временно отключите context processor:

В `config/settings.py` закомментируйте строку:
```python
# 'core.context_processors.seo_processor',
```

Затем перезапустите приложение.

## Проверка после исправления

1. Откройте сайт: http://onesim8n.beget.tech
2. Проверьте, что страница загружается
3. Проверьте исходный код страницы (Ctrl+U) - должны быть SEO теги в `<head>`

## Если проблема не решена

1. Проверьте логи на наличие ошибок Python
2. Убедитесь, что все файлы синхронизированы с сервером
3. Проверьте, что миграции применены (если были изменения в моделях)
4. Проверьте права доступа к файлам
