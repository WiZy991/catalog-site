# Проверка и перезапуск CommerceML обмена

## Проверка файла urls.py на сервере

Выполните на сервере:

```bash
cd ~/onesimus/onesimus
cat config/urls.py | grep -A 3 "cml/exchange"
```

Должны увидеть:
```python
    # Стандартный протокол CommerceML 2 обмена с 1С (должен быть ДО других путей)
    path('cml/exchange/', commerceml_views.commerceml_exchange, name='commerceml_exchange'),
    path('cml/exchange', commerceml_views.commerceml_views.commerceml_exchange, name='commerceml_exchange_no_slash'),
```

## Способы перезапуска Django

### Вариант 1: Если используете gunicorn/uwsgi через systemd (но sudo недоступен)

Попробуйте без sudo (если у вас есть права):
```bash
systemctl --user restart django
```

Или найдите процесс и перезапустите:
```bash
ps aux | grep gunicorn
# или
ps aux | grep uwsgi
# или
ps aux | grep manage.py
```

### Вариант 2: Если запускаете через screen/tmux

Найдите сессию:
```bash
screen -ls
# или
tmux ls
```

Войдите в сессию и перезапустите (Ctrl+C, затем запустите заново)

### Вариант 3: Если используете supervisor

```bash
supervisorctl restart django
# или
supervisorctl restart all
```

### Вариант 4: Если используете beget панель

1. Зайдите в панель управления beget
2. Найдите раздел "Процессы" или "Управление сайтом"
3. Перезапустите приложение Django

### Вариант 5: Убить процесс и запустить заново

```bash
# Найти процесс
ps aux | grep "manage.py runserver\|gunicorn\|uwsgi" | grep -v grep

# Убить процесс (замените PID на реальный)
kill -HUP <PID>

# Или найти и убить все процессы Django
pkill -f "manage.py runserver"
pkill -f gunicorn
pkill -f uwsgi
```

Затем запустите заново (в зависимости от вашей конфигурации).

## Проверка после перезапуска

После перезапуска проверьте:

```bash
python manage.py shell
>>> from django.urls import get_resolver
>>> resolver = get_resolver()
>>> patterns = [str(p.pattern) for p in resolver.url_patterns]
>>> [p for p in patterns if 'cml' in p]
```

Должны увидеть `['cml/exchange/', 'cml/exchange', '1c_exchange.php']`

## Альтернатива: Проверка через curl

После перезапуска проверьте URL:

```bash
curl -I "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth"
```

Должен вернуть не 404, а либо 401 (не авторизован) либо 200 (если авторизация прошла).

## Если ничего не помогает

Проверьте, что файл `config/urls.py` на сервере содержит правильные пути. Возможно, нужно синхронизировать файлы с сервера.
