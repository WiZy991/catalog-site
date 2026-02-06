# Детальная диагностика 502 Bad Gateway

## Проблема
Сайт возвращает 502 Bad Gateway даже после исправления отступов. Это означает, что Django приложение не может запуститься.

## Пошаговая диагностика

### Шаг 1: Проверьте синтаксис файла services.py на сервере

**Через SSH (если есть доступ):**
```bash
cd ~/onesimus/onesimus
source venv/bin/activate  # если используется виртуальное окружение
python -m py_compile catalog/services.py
```

**Через терминал в панели управления Beget:**
1. Найдите раздел "Терминал" или "SSH" в панели управления
2. Выполните те же команды

**Если есть ошибка синтаксиса:**
- Вы увидите сообщение с номером строки и описанием ошибки
- Исправьте ошибку и повторите проверку

### Шаг 2: Проверьте логи приложения

**Через панель управления Beget:**
1. Войдите в панель управления
2. Найдите раздел "Логи" или "Error logs"
3. Откройте последние логи ошибок
4. Ищите строки с:
   - `IndentationError`
   - `SyntaxError`
   - `ImportError`
   - `ModuleNotFoundError`
   - `NameError`

**Через SSH:**
```bash
cd ~/onesimus/onesimus

# Проверьте логи Django (если есть)
ls -la logs/
tail -n 100 logs/*.log

# Проверьте логи веб-сервера
tail -n 100 /var/log/nginx/error.log
# или
tail -n 100 /var/log/apache2/error.log

# Проверьте логи Passenger (если используется)
tail -n 100 ~/logs/passenger.log
```

### Шаг 3: Проверьте, что все зависимости установлены

```bash
cd ~/onesimus/onesimus
source venv/bin/activate  # если используется виртуальное окружение

# Проверьте, что Django установлен
python -c "import django; print(django.get_version())"

# Проверьте, что все модули импортируются
python -c "from catalog import services"
```

**Если есть ошибка импорта:**
- Установите недостающие пакеты: `pip install -r requirements.txt`

### Шаг 4: Попробуйте запустить Django вручную

```bash
cd ~/onesimus/onesimus
source venv/bin/activate  # если используется виртуальное окружение

# Попробуйте выполнить команду Django
python manage.py check

# Или попробуйте импортировать настройки
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); import django; django.setup()"
```

**Если есть ошибка:**
- Вы увидите точное сообщение об ошибке
- Исправьте проблему согласно сообщению

### Шаг 5: Проверьте конфигурацию WSGI

```bash
cd ~/onesimus/onesimus

# Проверьте файл config/wsgi.py
cat config/wsgi.py

# Должно быть:
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
```

### Шаг 6: Проверьте права доступа

```bash
cd ~/onesimus/onesimus

# Проверьте права на файлы
ls -la catalog/services.py
ls -la config/settings.py
ls -la manage.py

# Должны быть права на чтение (минимум 644)
chmod 644 catalog/services.py
chmod 644 config/settings.py
chmod 755 manage.py
```

### Шаг 7: Временно переименуйте services.py

Если ничего не помогает, попробуйте временно отключить services.py:

```bash
cd ~/onesimus/onesimus
mv catalog/services.py catalog/services.py.backup
touch tmp/restart.txt
```

**Если сайт заработал:**
- Проблема точно в services.py
- Восстановите файл: `mv catalog/services.py.backup catalog/services.py`
- Проверьте файл на ошибки более тщательно

**Если сайт всё ещё не работает:**
- Проблема в другом месте (settings.py, models.py, views.py и т.д.)

## Быстрое решение через файловый менеджер Beget

Если у вас нет доступа к SSH, но есть файловый менеджер:

1. **Создайте тестовый файл для проверки:**
   - Создайте файл `test_syntax.py` в корне проекта
   - Добавьте туда:
   ```python
   import sys
   sys.path.insert(0, '/home/o/onesim8n/onesimus/onesimus')
   try:
       from catalog import services
       print("OK: services.py импортируется без ошибок")
   except Exception as e:
       print(f"ERROR: {e}")
   ```

2. **Проверьте логи через панель управления:**
   - Обязательно найдите раздел с логами
   - Скопируйте последние ошибки
   - Они покажут точную причину проблемы

## Частые причины 502 Bad Gateway:

1. **Синтаксическая ошибка в Python коде** - проверьте через `python -m py_compile`
2. **Ошибка импорта модуля** - проверьте, что все зависимости установлены
3. **Ошибка в settings.py** - проверьте настройки Django
4. **Приложение не перезапустилось** - убедитесь, что `tmp/restart.txt` был создан/обновлен
5. **Проблемы с виртуальным окружением** - проверьте, что оно активировано
6. **Недостаточно памяти** - проверьте использование ресурсов в панели Beget

## Что делать прямо сейчас:

1. **Откройте логи в панели управления Beget** - это самый быстрый способ найти проблему
2. **Скопируйте последние ошибки из логов** - они покажут точную причину
3. **Проверьте синтаксис через терминал** (если есть доступ)

Без доступа к логам невозможно точно определить причину 502 ошибки!
