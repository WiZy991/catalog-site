# СРОЧНО: Синхронизация фронтенда

## Выполните ЭТИ команды на локальной машине:

```powershell
cd c:\Users\Антон\Desktop\web

# 1. Проверьте, что изменено
git status

# 2. Добавьте ВСЕ изменения (включая CSS/JS)
git add .

# 3. Закоммитьте
git commit -m "Синхронизация фронтенда с продакшеном"

# 4. Отправьте на сервер
git push origin main
```

## Затем на сервере выполните:

```bash
cd ~/onesimus/onesimus

# 1. Загрузите изменения
git pull origin main

# 2. КРИТИЧНО: Соберите статические файлы
python manage.py collectstatic --noinput --clear

# 3. Перезапустите
touch tmp/restart.txt

# 4. Проверьте
cat staticfiles/css/style.css | head -30
```

## Если collectstatic не помог:

```bash
# Принудительно пересоберите
rm -rf staticfiles/*
python manage.py collectstatic --noinput
touch tmp/restart.txt
```

## Проверка на сервере:

```bash
# Сравните даты изменения
ls -lh static/css/style.css staticfiles/css/style.css

# Проверьте содержимое
head -50 staticfiles/css/style.css
```

**Главное:** После каждого изменения в CSS/JS ОБЯЗАТЕЛЬНО выполняйте `collectstatic` на сервере!
