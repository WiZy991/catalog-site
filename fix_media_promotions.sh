#!/bin/bash
# Скрипт для исправления проблем с медиа-файлами акций

echo "=== Создание директории для медиа-файлов акций ==="
mkdir -p media/promotions
chmod 755 media/promotions

echo ""
echo "=== Проверка существующих акций в БД ==="
python manage.py shell << EOF
from catalog.models import Promotion
promos = Promotion.objects.all()
print(f"Всего акций: {promos.count()}")
for p in promos:
    if p.image:
        print(f"ID: {p.id}, Image path: {p.image.name}, URL: {p.image.url}, Exists: {p.image.storage.exists(p.image.name)}")
    else:
        print(f"ID: {p.id}, No image")
EOF

echo ""
echo "=== Проверка директорий ==="
ls -la media/ 2>/dev/null || echo "Директория media/ не существует"
ls -la static/promotions/ 2>/dev/null || echo "Директория static/promotions/ не существует"

echo ""
echo "=== Проверка настроек ==="
python manage.py shell << EOF
from django.conf import settings
print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"STATIC_URL: {settings.STATIC_URL}")
EOF
