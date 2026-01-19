# Исправление ошибки "Reverse for 'consent' not found"

## Проблема
При оформлении заказа возникает ошибка:
```
NoReverseMatch: Reverse for 'consent' not found. 'consent' is not a valid view function or pattern name.
```

## Причина
На сервере используется старая версия кода или кэш шаблонов, где `'consent'` используется без namespace `'core:'`.

## Решение

### Шаг 1: Обновите код на сервере

```bash
cd ~/onesimus/onesimus
git pull origin main
```

### Шаг 2: Очистите кэш Python

```bash
# Найти и удалить файлы .pyc
find . -type d -name __pycache__ -exec rm -r {} +
find . -name "*.pyc" -delete
```

### Шаг 3: Перезапустите приложение

```bash
mkdir -p tmp
touch tmp/restart.txt
```

### Шаг 4: Проверьте, что все URL правильно настроены

Убедитесь, что в `core/urls.py` есть:
```python
app_name = 'core'
path('consent/', views.ConsentView.as_view(), name='consent'),
```

И в `config/urls.py`:
```python
path('', include('core.urls')),
```

### Шаг 5: Проверьте шаблоны

Убедитесь, что во всех шаблонах используется:
```django
{% url 'core:consent' %}
```

А не:
```django
{% url 'consent' %}
```

## Быстрая проверка

Выполните на сервере:
```bash
cd ~/onesimus/onesimus
# Проверьте, что используется правильный namespace
grep -r "url.*consent" templates/ | grep -v "core:consent"
# Если есть результаты - исправьте их на 'core:consent'

# Обновите код
git pull origin main

# Перезапустите
touch tmp/restart.txt
```

## Если проблема сохраняется

1. Проверьте версию Django на сервере
2. Убедитесь, что все миграции применены
3. Проверьте логи сервера для дополнительной информации
