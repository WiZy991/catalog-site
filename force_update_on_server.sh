#!/bin/bash
# Принудительное обновление на сервере

cd ~/onesimus/onesimus

echo "=== 1. Загрузка изменений из репозитория ==="
git pull

echo ""
echo "=== 2. Обновление STATIC_VERSION ==="
sed -i "s/STATIC_VERSION = '.*'/STATIC_VERSION = '1.3'/" config/settings.py
grep "STATIC_VERSION" config/settings.py

echo ""
echo "=== 3. Проверка CSS файлов ==="
echo "Проверка border-radius для категорий:"
grep -c "border-radius: 50%" static/css/style.css
echo "Проверка aspect-ratio для корзины:"
grep -c "aspect-ratio.*1 / 1" static/css/style.css
echo "Проверка стилей карусели:"
grep -A 5 "promotions-carousel__slide" static/css/style.css | head -10

echo ""
echo "=== 4. Создание директории для медиа-файлов ==="
mkdir -p media/promotions
chmod 755 media/promotions

echo ""
echo "=== 5. Проверка акций в БД ==="
python manage.py shell << 'PYEOF'
from catalog.models import Promotion
promos = Promotion.objects.filter(is_active=True)
print(f"Активных акций: {promos.count()}")
for p in promos:
    if p.image:
        print(f"ID: {p.id}, Title: {p.title}, Image: {p.image.name}")
        print(f"  Full path: {p.image.path if hasattr(p.image, 'path') else 'N/A'}")
        print(f"  URL: {p.image.url}")
PYEOF

echo ""
echo "=== 6. Перезапуск приложения ==="
# Найдите правильный способ перезапуска
if [ -f "../tmp/restart.txt" ]; then
    touch ../tmp/restart.txt
    echo "Файл restart.txt обновлен"
elif [ -f "tmp/restart.txt" ]; then
    touch tmp/restart.txt
    echo "Файл restart.txt обновлен"
else
    echo "Создание директории tmp и файла restart.txt"
    mkdir -p tmp
    touch tmp/restart.txt
fi

echo ""
echo "=== 7. Финальная проверка настроек ==="
python manage.py shell << 'PYEOF'
from django.conf import settings
print(f"STATIC_VERSION: {getattr(settings, 'STATIC_VERSION', 'NOT SET')}")
print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")
PYEOF

echo ""
echo "=== Готово! ==="
echo "Теперь откройте сайт в браузере и нажмите Ctrl+Shift+R для жесткой перезагрузки"
echo "Или откройте в режиме инкогнито"
