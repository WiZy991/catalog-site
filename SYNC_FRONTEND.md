# Синхронизация фронтенд изменений с продакшеном

## Проблема: изменения в CSS/JS не отображаются на продакшене

### Шаг 1: Проверьте, что изменения закоммичены

```powershell
# Проверьте статус
git status

# Если есть незакоммиченные изменения в CSS/JS:
git add static/css/* static/js/* templates/*
git commit -m "Обновление фронтенда: [опишите что изменили]"
git push origin main
```

### Шаг 2: На сервере выполните

```bash
cd ~/onesimus/onesimus

# 1. Загрузите изменения
git pull origin main

# 2. ВАЖНО: Соберите статические файлы (это критично для CSS/JS!)
python manage.py collectstatic --noinput

# 3. Перезапустите приложение
touch tmp/restart.txt
```

### Шаг 3: Проверьте на сервере

```bash
# Проверьте, что CSS файлы обновились
ls -la static/css/style.css
cat static/css/style.css | head -20

# Проверьте, что файлы в staticfiles (собранные)
ls -la staticfiles/css/style.css
cat staticfiles/css/style.css | head -20

# Проверьте дату изменения файлов
stat static/css/style.css
stat staticfiles/css/style.css
```

## Важно!

**`collectstatic` ОБЯЗАТЕЛЬНО нужно выполнять после каждого изменения в CSS/JS!**

Django копирует файлы из `static/` в `staticfiles/`, и веб-сервер обслуживает файлы из `staticfiles/`, а не из `static/`.

## Если изменения всё ещё не применяются:

1. **Проверьте, что файлы действительно изменились на сервере:**
   ```bash
   # Сравните содержимое
   diff static/css/style.css staticfiles/css/style.css
   ```

2. **Принудительно пересоберите статику:**
   ```bash
   # Удалите старые файлы и соберите заново
   rm -rf staticfiles/css/*
   python manage.py collectstatic --noinput --clear
   ```

3. **Проверьте права доступа:**
   ```bash
   chmod -R 755 staticfiles/
   ```

4. **Очистите кеш браузера:**
   - Нажмите Ctrl+Shift+R (жесткая перезагрузка)
   - Или откройте в режиме инкогнито

5. **Проверьте конфигурацию веб-сервера:**
   Убедитесь, что nginx/apache обслуживает `/static/` из директории `staticfiles/`

## Автоматический скрипт для сервера

Создайте файл `update_frontend.sh` на сервере:

```bash
#!/bin/bash
cd ~/onesimus/onesimus
git pull origin main
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
echo "Фронтенд обновлен!"
```

Затем запускайте:
```bash
bash update_frontend.sh
```
