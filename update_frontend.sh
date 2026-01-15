#!/bin/bash
# Скрипт для обновления фронтенда на сервере

cd ~/onesimus/onesimus

echo "=== 1. Загрузка изменений ==="
git pull origin main

echo ""
echo "=== 2. Принудительная пересборка статических файлов ==="
# Удаляем старые файлы и собираем заново
rm -rf staticfiles/css/*
rm -rf staticfiles/js/*
python manage.py collectstatic --noinput --clear

echo ""
echo "=== 3. Проверка обновления ==="
echo "Дата изменения style.css:"
ls -lh staticfiles/css/style.css 2>/dev/null || echo "Файл не найден!"

echo ""
echo "=== 4. Перезапуск приложения ==="
mkdir -p tmp
touch tmp/restart.txt

echo ""
echo "=== Готово! ==="
echo "Проверьте сайт в браузере (Ctrl+Shift+R для очистки кеша)"
