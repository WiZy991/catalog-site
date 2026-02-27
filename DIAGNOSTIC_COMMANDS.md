# Команды для диагностики сервера

## 1. Проверка синтаксиса Python файлов

```bash
cd ~/onesimus/onesimus
python3 -m py_compile catalog/commerceml_views.py
python3 -m py_compile core/views.py
python3 -m py_compile catalog/models.py
python3 -m py_compile catalog/admin.py
```

## 2. Проверка логов Django

```bash
# Последние 100 строк логов Django
tail -n 100 ~/onesimus/onesimus/log_django.txt

# Или если логи в другом месте
tail -n 100 ~/onesimus/onesimus/logs/*.log

# Поиск ошибок в логах
grep -i "error\|exception\|traceback" ~/onesimus/onesimus/log_django.txt | tail -n 50
```

## 3. Проверка логов веб-сервера (Nginx/Apache)

```bash
# Nginx
tail -n 100 /var/log/nginx/error.log
tail -n 100 /var/log/nginx/access.log

# Apache (если используется)
tail -n 100 /var/log/apache2/error.log
```

## 4. Проверка логов Passenger (если используется)

```bash
# Логи Passenger
tail -n 100 ~/onesimus/onesimus/log/passenger.log

# Или системные логи
tail -n 100 /var/log/passenger.log
```

## 5. Проверка процесса Django

```bash
# Проверка запущенных процессов Python
ps aux | grep python

# Проверка процессов Passenger
ps aux | grep passenger
```

## 6. Проверка импорта модулей Django

```bash
cd ~/onesimus/onesimus
source venv/bin/activate
python manage.py check

# Проверка конкретного модуля
python -c "import catalog.commerceml_views"
python -c "import core.views"
```

## 7. Проверка базы данных

```bash
cd ~/onesimus/onesimus
source venv/bin/activate
python manage.py dbshell
# В SQLite shell:
# .tables
# .quit
```

## 8. Перезапуск приложения

```bash
cd ~/onesimus/onesimus
touch tmp/restart.txt

# Или если используется systemd
sudo systemctl restart onesimus

# Или если используется supervisor
sudo supervisorctl restart onesimus
```

## 9. Проверка прав доступа к файлам

```bash
cd ~/onesimus/onesimus
ls -la catalog/commerceml_views.py
ls -la core/views.py
ls -la catalog/models.py
```

## 10. Полная проверка Django

```bash
cd ~/onesimus/onesimus
source venv/bin/activate
python manage.py check --deploy
python manage.py validate
```
