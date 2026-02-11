# Инструкция по перезапуску Django сервера на beget

## Проверка текущих процессов

Выполните на сервере:

```bash
# Найти все процессы Django/Python
ps aux | grep -E "python|gunicorn|uwsgi|manage.py" | grep -v grep

# Или более детально
ps aux | grep python | grep -v grep
```

## Способы перезапуска

### Вариант 1: Если используете gunicorn/uwsgi

```bash
# Найти процесс
ps aux | grep gunicorn | grep -v grep
# или
ps aux | grep uwsgi | grep -v grep

# Отправить сигнал HUP для перезагрузки (не убивает процесс)
kill -HUP <PID>

# Или найти и перезагрузить все процессы gunicorn
pkill -HUP gunicorn
pkill -HUP uwsgi
```

### Вариант 2: Если используете supervisor

```bash
# Проверить статус
supervisorctl status

# Перезапустить
supervisorctl restart django
# или все процессы
supervisorctl restart all
```

### Вариант 3: Если используете systemd (без sudo)

```bash
# Попробовать без sudo (если есть права)
systemctl --user restart django

# Или через systemctl без sudo (если настроено)
systemctl restart django
```

### Вариант 4: Если запускаете вручную через screen/tmux

```bash
# Найти сессии
screen -ls
# или
tmux ls

# Войти в сессию
screen -r <session_name>
# или
tmux attach -t <session_name>

# В сессии нажать Ctrl+C для остановки
# Затем запустить заново:
python manage.py runserver 0.0.0.0:8000
# или
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

### Вариант 5: Через beget панель

1. Зайдите в панель управления beget: https://cp.beget.com
2. Найдите ваш сайт
3. Перейдите в раздел "Управление сайтом" или "Процессы"
4. Найдите процесс Django/Python
5. Нажмите "Перезапустить" или "Остановить" → "Запустить"

### Вариант 6: Полный перезапуск (убить и запустить заново)

```bash
# Найти все процессы Python, связанные с Django
ps aux | grep "manage.py\|gunicorn\|uwsgi" | grep -v grep

# Убить процессы (замените PID на реальные)
kill <PID1> <PID2> ...

# Или убить все процессы gunicorn/uwsgi
pkill -f gunicorn
pkill -f uwsgi
pkill -f "manage.py runserver"

# Затем запустить заново (в зависимости от вашей конфигурации)
# Обычно это делается через:
# - supervisor
# - systemd
# - screen/tmux
# - или через beget панель
```

## Проверка после перезапуска

После перезапуска проверьте:

```bash
# 1. Проверить, что URL зарегистрированы
python manage.py shell
>>> from django.urls import get_resolver
>>> resolver = get_resolver()
>>> patterns = [str(p.pattern) for p in resolver.url_patterns]
>>> [p for p in patterns if 'cml' in p]
# Должны увидеть: ['cml/exchange/', 'cml/exchange', '1c_exchange.php']

# 2. Проверить через curl
curl -I "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth"
# Должен вернуть не 404, а 401 (не авторизован) или 200
```

## Если ничего не помогает

Проверьте логи приложения:

```bash
# Найти логи (обычно в одном из этих мест)
tail -f ~/logs/django.log
tail -f ~/logs/error.log
tail -f /var/log/gunicorn/error.log
tail -f ~/onesimus/onesimus/logs/*.log

# Или если используете supervisor
supervisorctl tail -f django
```

## Быстрая проверка конфигурации

Убедитесь, что все файлы на месте:

```bash
cd ~/onesimus/onesimus

# Проверить файл urls.py
cat config/urls.py | grep "cml/exchange"

# Проверить файл commerceml_views.py
ls -la catalog/commerceml_views.py

# Проверить импорт
python manage.py shell
>>> from catalog import commerceml_views
>>> print(commerceml_views.commerceml_exchange)
```
