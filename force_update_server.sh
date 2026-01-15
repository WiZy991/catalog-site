#!/bin/bash
# Скрипт для принудительного обновления на сервере

cd ~/onesimus/onesimus

echo "=== Проверка текущей директории ==="
pwd

echo ""
echo "=== Сохранение текущих изменений (если есть) ==="
git stash

echo ""
echo "=== Загрузка изменений ==="
git fetch origin main

echo ""
echo "=== Принудительное обновление ==="
git reset --hard origin/main

echo ""
echo "=== Проверка файлов ==="
echo "Проверка main.js:"
grep -n "AUTOPLAY_DELAY = 5000" static/js/main.js || echo "⚠ main.js не найден или не содержит AUTOPLAY_DELAY"

echo ""
echo "Проверка style.css:"
grep -c "promotions-carousel" static/css/style.css || echo "⚠ style.css не найден"

echo ""
echo "Проверка STATIC_VERSION:"
grep "STATIC_VERSION" config/settings.py

echo ""
echo "=== Очистка старых статических файлов ==="
rm -rf staticfiles/*

echo ""
echo "=== Сбор статических файлов ==="
python manage.py collectstatic --noinput --clear

echo ""
echo "=== Проверка собранных файлов ==="
if [ -f "staticfiles/js/main.js" ]; then
    echo "✓ staticfiles/js/main.js существует"
    grep -n "AUTOPLAY_DELAY = 5000" staticfiles/js/main.js || echo "⚠ AUTOPLAY_DELAY не найден в собранном файле"
else
    echo "✗ staticfiles/js/main.js НЕ существует!"
fi

if [ -f "staticfiles/css/style.css" ]; then
    echo "✓ staticfiles/css/style.css существует"
    grep -c "promotions-carousel" staticfiles/css/style.css || echo "⚠ promotions-carousel не найден"
else
    echo "✗ staticfiles/css/style.css НЕ существует!"
fi

echo ""
echo "=== Перезапуск приложения ==="
mkdir -p tmp
touch tmp/restart.txt

echo ""
echo "=== Готово! ==="
echo "Проверьте сайт и очистите кеш браузера (Ctrl+F5)"
