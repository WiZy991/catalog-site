# Срочное исправление ошибки 502 Bad Gateway

## Проблема
Сайт показывает ошибку "502 Bad Gateway" и "Incomplete response received from application". Это означает, что Django приложение не запущено или упало с ошибкой.

## Причина
Скорее всего, проблема связана с:
1. Новыми моделями, которые требуют миграций
2. Конфликтом имен в serializers.py (исправлено)
3. Приложение не перезапущено после изменений

## Решение

### Шаг 1: Исправление кода (уже сделано)
✅ Исправлен конфликт имен `ValidationError` в `catalog/serializers.py`

### Шаг 2: На сервере выполните следующие команды

Подключитесь к серверу по SSH и выполните:

```bash
# 1. Перейдите в директорию проекта
cd ~/onesimus/onesimus

# 2. Активируйте виртуальное окружение
source venv/bin/activate

# 3. Загрузите последние изменения (если есть)
git pull origin main

# 4. ВАЖНО: Выполните миграции для новых моделей
python manage.py makemigrations catalog
python manage.py migrate

# 5. Соберите статические файлы
python manage.py collectstatic --noinput

# 6. Проверьте, нет ли синтаксических ошибок
python manage.py check

# 7. Перезапустите приложение
# Для Beget обычно это:
touch tmp/restart.txt

# Или если используется systemd:
# sudo systemctl restart your-service-name

# Или если используется supervisor:
# sudo supervisorctl restart your-app-name
```

### Шаг 3: Проверьте логи

```bash
# Логи Django (если настроены)
tail -f logs/django.log

# Или логи веб-сервера
tail -f /var/log/nginx/error.log
# или
tail -f /var/log/apache2/error.log

# Или логи приложения (зависит от конфигурации)
tail -f ~/onesimus/onesimus/logs/*.log
```

### Шаг 4: Проверьте, что приложение запущено

```bash
# Проверьте процессы Python
ps aux | grep python
ps aux | grep gunicorn
ps aux | grep uwsgi

# Проверьте, слушает ли приложение порт
netstat -tulpn | grep python
# или
ss -tulpn | grep python
```

## Альтернативное решение: временно отключить новые модели

Если миграции не выполняются, можно временно закомментировать новые модели:

### В `catalog/models.py`:

Найдите строки с `ProductCharacteristic` и `SyncLog` и временно закомментируйте их регистрацию в админке.

### В `catalog/admin.py`:

Закомментируйте:
```python
# @admin.register(ProductCharacteristic)
# class ProductCharacteristicAdmin(admin.ModelAdmin):
#     ...

# @admin.register(SyncLog)
# class SyncLogAdmin(admin.ModelAdmin):
#     ...
```

### В `catalog/one_c_views.py`:

Временно закомментируйте импорты и использование:
```python
# from .models import Product, ProductCharacteristic, Category, SyncLog
from .models import Product, Category  # Временно без новых моделей

# И закомментируйте использование SyncLog в коде
```

## Быстрая проверка на локальной машине

Перед отправкой на сервер проверьте локально:

```bash
# 1. Проверьте синтаксис
python manage.py check

# 2. Попробуйте выполнить миграции
python manage.py makemigrations
python manage.py migrate

# 3. Запустите сервер
python manage.py runserver

# 4. Проверьте, что сайт открывается
# Откройте http://localhost:8000
```

## Если ничего не помогает

1. **Откатите изменения:**
   ```bash
   git log  # Найдите последний рабочий коммит
   git checkout <commit-hash>  # Откатитесь к нему
   ```

2. **Проверьте конфигурацию веб-сервера:**
   - Убедитесь, что путь к приложению правильный
   - Проверьте права доступа к файлам
   - Проверьте, что виртуальное окружение активировано

3. **Обратитесь к хостинг-провайдеру (Beget):**
   - Проверьте панель управления Beget
   - Посмотрите логи в панели управления
   - Проверьте статус приложения

## После исправления

Когда сайт заработает:

1. ✅ Выполните миграции
2. ✅ Проверьте работу админки
3. ✅ Проверьте работу API: `/api/1c/sync/`
4. ✅ Проверьте логи синхронизации: `/admin/catalog/synclog/`

## Важно!

**Не тестируйте интеграцию 1С, пока сайт не работает!**

Сначала исправьте ошибку 502, затем:
1. Убедитесь, что сайт открывается
2. Убедитесь, что админка работает
3. Только потом тестируйте API интеграции
