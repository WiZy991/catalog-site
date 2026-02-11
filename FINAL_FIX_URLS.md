# Финальное исправление проблемы с URL

## Проблема
URL видны в shell, но не видны через веб-запрос. Passenger использует старую версию.

## Решение

### Шаг 1: Проверьте начало файла urls.py

```bash
cd ~/onesimus/onesimus
head -35 config/urls.py
```

Должны увидеть в начале `urlpatterns` строки с `cml/exchange/`.

### Шаг 2: Проверьте, что импорт работает без ошибок

```bash
python manage.py shell
```

В shell:
```python
# Проверка без ошибок
from catalog import commerceml_views
from config.urls import urlpatterns

# Проверка, что пути в начале
for i, p in enumerate(urlpatterns[:5]):
    if hasattr(p, 'pattern'):
        print(f"{i+1}. {p.pattern}")
```

### Шаг 3: Принудительно убейте все процессы Passenger

```bash
# Найти все процессы
ps aux | grep -E "passenger|python.*manage|gunicorn" | grep -v grep

# Убить все процессы Passenger
pkill -9 passenger
pkill -9 -f "passenger"

# Подождать
sleep 10
```

### Шаг 4: Очистите все кеши и перезапустите

```bash
cd ~/onesimus/onesimus

# Очистить кеш
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Перезапустить
mkdir -p tmp
touch tmp/restart.txt
touch tmp/always_restart.txt
rm -f tmp/stop.txt 2>/dev/null

# Подождать 15 секунд
sleep 15
```

### Шаг 5: Проверьте через несколько запросов

```bash
# Сделайте несколько запросов к разным URL
for i in {1..5}; do
    curl -I "http://onesim8n.beget.tech/" > /dev/null 2>&1
    sleep 2
done

# Проверьте CommerceML
curl -v "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth"
```

### Шаг 6: Если ничего не помогает - проверьте через beget панель

Возможно, нужно перезапустить через панель управления beget, так как Passenger может быть настроен там.
