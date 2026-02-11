# Принудительный перезапуск на beget

## Проблема
Паттерны видны в shell, но не в веб-запросе. Passenger использует старую версию кода.

## Решение

### Шаг 1: Проверьте, что файл действительно обновлен

```bash
cd ~/onesimus/onesimus
head -45 config/urls.py | tail -10
```

Должны увидеть строки с `cml/exchange/`.

### Шаг 2: Очистите все кеши Python

```bash
cd ~/onesimus/onesimus

# Удалить все .pyc файлы
find . -type f -name "*.pyc" -delete

# Удалить все __pycache__ директории
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Удалить .pyo файлы
find . -type f -name "*.pyo" -delete
```

### Шаг 3: Принудительный перезапуск Passenger

```bash
# Создать файлы перезапуска
mkdir -p tmp
touch tmp/restart.txt
touch tmp/always_restart.txt
touch tmp/stop.txt
rm -f tmp/stop.txt

# Подождать
sleep 5
```

### Шаг 4: Найти и убить процесс Passenger

```bash
# Найти все процессы Passenger
ps aux | grep -i passenger | grep -v grep

# Найти процессы Python, связанные с Django
ps aux | grep python | grep -v grep | grep -v "manage.py shell"

# Если нашли процесс Passenger, убейте его
# (замените PID на реальный)
kill -9 <PID>

# Или убейте все процессы Passenger
pkill -9 passenger
```

### Шаг 5: Проверьте через несколько запросов

```bash
# Сделайте несколько запросов к разным URL, чтобы Passenger перезагрузился
curl -I "http://onesim8n.beget.tech/"
sleep 2
curl -I "http://onesim8n.beget.tech/admin/"
sleep 2
curl -I "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth"
```

### Шаг 6: Альтернатива - проверьте, нет ли другого файла urls.py

```bash
# Найти все файлы urls.py
find . -name "urls.py" -type f

# Проверьте, какой файл используется
python manage.py shell
>>> import sys
>>> sys.path
>>> import config.urls
>>> print(config.urls.__file__)
```

### Шаг 7: Если ничего не помогает - добавьте URL в другом месте

Можно временно добавить URL в `core/urls.py` или создать отдельный файл для тестирования.
