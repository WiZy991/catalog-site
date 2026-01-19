# Быстрое исправление ошибки "consent not found"

## Проблема
При оформлении заказа: `Reverse for 'consent' not found`

## Решение (выполните на сервере)

```bash
cd ~/onesimus/onesimus

# 1. Обновите код с GitHub
git pull origin main

# 2. Очистите кэш Python
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 3. Перезапустите приложение
mkdir -p tmp
touch tmp/restart.txt
```

## Проверка

После обновления проверьте, что в `core/urls.py` есть:
- `app_name = 'core'`
- `path('consent/', views.ConsentView.as_view(), name='consent')`

И в шаблонах используется `{% url 'core:consent' %}` (с namespace).

## Если не помогло

Проверьте, что на сервере все изменения залиты:
```bash
git status
git log --oneline -5
```

Если есть неотправленные коммиты, отправьте их:
```bash
git push origin main
```
