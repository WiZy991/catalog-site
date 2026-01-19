# Исправление страницы "Согласие на обработку персональных данных"

## Проблема
Страница согласия не работает, хотя категории и товары отображаются.

## Причина
На сервере старая версия кода, где отсутствует или неправильно настроена страница согласия.

## Решение

### Шаг 1: Проверьте текущее состояние на сервере

```bash
cd ~/onesimus/onesimus

# Проверьте, есть ли URL для consent
grep -n "consent" core/urls.py

# Проверьте, есть ли view
grep -n "ConsentView" core/views.py

# Проверьте, есть ли шаблон
ls -la templates/core/consent.html
```

### Шаг 2: Обновите код на сервере

```bash
cd ~/onesimus/onesimus

# Получите последние изменения с GitHub
git pull origin main

# Если есть конфликты или нужно принудительно обновить:
git fetch origin main
git reset --hard origin/main
```

### Шаг 3: Очистите кэш

```bash
# Очистите кэш Python
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Очистите кэш Django (если используется)
python manage.py clear_cache 2>/dev/null || echo "Команда clear_cache не найдена"
```

### Шаг 4: Перезапустите приложение

```bash
mkdir -p tmp
touch tmp/restart.txt
```

### Шаг 5: Проверьте работу

Откройте в браузере:
- `http://onesim8n.beget.tech/consent/` - должна открыться страница согласия

## Что должно быть в коде

### core/urls.py
```python
app_name = 'core'

urlpatterns = [
    # ... другие URL ...
    path('consent/', views.ConsentView.as_view(), name='consent'),
]
```

### core/views.py
```python
class ConsentView(TemplateView):
    """Страница Согласия на обработку персональных данных."""
    template_name = 'core/consent.html'
```

### config/urls.py
```python
urlpatterns = [
    # ...
    path('', include('core.urls')),
    # ...
]
```

### templates/core/consent.html
Файл должен существовать и содержать HTML разметку страницы согласия.

## Если проблема сохраняется

1. **Проверьте логи сервера:**
   ```bash
   tail -f ~/logs/error.log
   # или
   journalctl -u your-service-name -f
   ```

2. **Проверьте, что все файлы на месте:**
   ```bash
   ls -la core/urls.py
   ls -la core/views.py
   ls -la templates/core/consent.html
   ```

3. **Проверьте версию кода:**
   ```bash
   git log --oneline -5
   git status
   ```

4. **Проверьте, что изменения залиты на GitHub:**
   ```bash
   git remote -v
   git fetch origin
   git log origin/main --oneline -5
   ```

## Быстрое исправление (если код не обновляется)

Если `git pull` не помогает, возможно нужно принудительно обновить:

```bash
cd ~/onesimus/onesimus

# Сохраните текущие изменения (если есть важные)
git stash

# Принудительно обновите с GitHub
git fetch origin main
git reset --hard origin/main

# Перезапустите
touch tmp/restart.txt
```

**⚠️ Внимание:** `git reset --hard` удалит все локальные изменения, которые не были закоммичены!
