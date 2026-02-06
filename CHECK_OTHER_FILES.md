# Проверка других файлов после исправления services.py

## Синтаксис services.py правильный ✅

Теперь нужно проверить другие возможные причины 502 Bad Gateway.

## Шаг 1: Проверьте импорт модулей

Выполните на сервере:

```bash
cd ~/onesimus/onesimus
source venv/bin/activate  # если используется виртуальное окружение

# Проверьте, что Django может импортировать services
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); import django; django.setup(); from catalog import services; print('OK: services импортируется')"
```

**Если есть ошибка:**
- Вы увидите точное сообщение об ошибке
- Это может быть проблема с models.py, settings.py или другими зависимостями

## Шаг 2: Проверьте другие Python файлы на синтаксические ошибки

```bash
cd ~/onesimus/onesimus

# Проверьте models.py
python -m py_compile catalog/models.py

# Проверьте views.py
python -m py_compile catalog/views.py

# Проверьте settings.py
python -m py_compile config/settings.py

# Проверьте urls.py
python -m py_compile config/urls.py
python -m py_compile catalog/urls.py
```

**Если есть ошибка в каком-то файле:**
- Исправьте её
- Перезапустите приложение: `touch tmp/restart.txt`

## Шаг 3: Проверьте, что Django может запуститься

```bash
cd ~/onesimus/onesimus
source venv/bin/activate  # если используется виртуальное окружение

# Попробуйте выполнить команду Django
python manage.py check

# Или попробуйте получить версию Django
python manage.py --version
```

**Если есть ошибка:**
- Вы увидите точное сообщение
- Это может быть проблема с настройками или зависимостями

## Шаг 4: Убедитесь, что приложение перезапустилось

```bash
cd ~/onesimus/onesimus

# Проверьте время последнего изменения restart.txt
ls -la tmp/restart.txt

# Если файла нет или он старый, создайте/обновите его
touch tmp/restart.txt

# Подождите 30 секунд и проверьте сайт
```

## Шаг 5: Проверьте логи приложения (ОБЯЗАТЕЛЬНО!)

**Через панель управления Beget:**
1. Найдите раздел "Логи" или "Error logs"
2. Откройте последние логи
3. Ищите ошибки, которые произошли после последнего перезапуска

**Через SSH:**
```bash
# Проверьте логи веб-сервера
tail -n 100 /var/log/nginx/error.log
# или
tail -n 100 /var/log/apache2/error.log

# Проверьте логи Passenger (если используется)
tail -n 100 ~/logs/passenger.log

# Проверьте логи Django (если есть)
ls -la logs/
tail -n 100 logs/*.log 2>/dev/null
```

## Шаг 6: Проверьте, что все зависимости установлены

```bash
cd ~/onesimus/onesimus
source venv/bin/activate  # если используется виртуальное окружение

# Проверьте, что Django установлен
python -c "import django; print(django.get_version())"

# Проверьте основные зависимости
python -c "import mptt; print('mptt OK')"
python -c "import django_filters; print('django_filters OK')"
python -c "from import_export import resources; print('import_export OK')"

# Если какая-то зависимость отсутствует, установите её
pip install -r requirements.txt
```

## Шаг 7: Временно отключите services.py (для диагностики)

Если ничего не помогает, попробуйте временно переименовать services.py:

```bash
cd ~/onesimus/onesimus
mv catalog/services.py catalog/services.py.backup

# Создайте минимальный файл
cat > catalog/services.py << 'EOF'
# Временный файл для диагностики
pass
EOF

# Перезапустите
touch tmp/restart.txt

# Подождите 30 секунд и проверьте сайт
```

**Если сайт заработал:**
- Проблема в services.py (возможно, runtime ошибка, а не синтаксическая)
- Восстановите файл: `mv catalog/services.py.backup catalog/services.py`
- Проверьте функции, которые вызываются при импорте модуля

**Если сайт всё ещё не работает:**
- Проблема в другом месте (settings.py, models.py, views.py и т.д.)

## Что делать прямо сейчас:

1. **Выполните команду из Шага 1** - проверка импорта модулей
2. **Проверьте логи (Шаг 5)** - это самый важный шаг!
3. **Выполните `python manage.py check`** - проверит конфигурацию Django

Логи покажут точную причину ошибки!
