# Инструкция по исправлению проблемы Git

## Проблема: "confused by unstable object source data"

Эта ошибка возникает из-за поврежденных объектов в репозитории Git.

## Решение 1: Восстановление репозитория

```bash
cd ~/onesimus/onesimus

# 1. Создайте резервную копию текущих изменений
cp -r . ../onesimus_backup

# 2. Попробуйте восстановить репозиторий
git fsck --full
git gc --prune=now --aggressive

# 3. Если не помогло, попробуйте удалить поврежденные объекты
# (ОСТОРОЖНО: это может привести к потере истории)
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 4. Попробуйте снова добавить файлы
git add catalog/commerceml_views.py
git add core/views.py
git add catalog/models.py
git add catalog/admin.py
```

## Решение 2: Добавление файлов по одному (обход проблемы)

Если восстановление не помогло, добавьте файлы по одному:

```bash
cd ~/onesimus/onesimus

# Добавляйте файлы по одному, пропуская проблемные
git add catalog/commerceml_views.py
git add core/views.py
git add catalog/models.py
git add catalog/admin.py

# Проверьте статус
git status
```

## Решение 3: Пересоздание репозитория (крайний случай)

Если ничего не помогает:

```bash
cd ~/onesimus/onesimus

# 1. Сохраните текущие изменения
git stash

# 2. Создайте новый репозиторий
cd ..
mv onesimus onesimus_old
git clone <URL_РЕПОЗИТОРИЯ> onesimus
cd onesimus

# 3. Скопируйте измененные файлы
cp ../onesimus_old/catalog/commerceml_views.py catalog/
cp ../onesimus_old/core/views.py core/
cp ../onesimus_old/catalog/models.py catalog/
cp ../onesimus_old/catalog/admin.py catalog/

# 4. Добавьте и закоммитьте
git add .
git commit -m "Fix: Стабильность подсчета товаров и производительность"
git push
```

## Решение 4: Исключение db.sqlite3 из отслеживания

Если db.sqlite3 уже был закоммичен ранее:

```bash
cd ~/onesimus/onesimus

# Удалите db.sqlite3 из индекса Git (но оставьте файл)
git rm --cached db.sqlite3

# Убедитесь, что он в .gitignore
echo "db.sqlite3" >> .gitignore

# Закоммитьте изменения
git add .gitignore
git commit -m "Remove db.sqlite3 from tracking"
```
