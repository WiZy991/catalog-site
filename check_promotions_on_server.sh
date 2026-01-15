#!/bin/bash
# Скрипт для проверки акций на сервере

cd ~/onesimus/onesimus

echo "=== Проверка акций в базе данных ==="
python manage.py shell << 'PYEOF'
from catalog.models import Promotion
from django.conf import settings

print(f"Всего акций в БД: {Promotion.objects.count()}")
print(f"Активных акций: {Promotion.objects.filter(is_active=True).count()}")

promos = Promotion.objects.all()
for p in promos:
    print(f"\nID: {p.id}")
    print(f"  Title: {p.title}")
    print(f"  Is active: {p.is_active}")
    print(f"  Order: {p.order}")
    if p.image:
        print(f"  Image name: {p.image.name}")
        print(f"  Image URL: {p.image.url}")
        # Проверка существования файла
        try:
            import os
            media_root = str(settings.MEDIA_ROOT)
            image_path = os.path.join(media_root, p.image.name)
            exists = os.path.exists(image_path)
            print(f"  Image path: {image_path}")
            print(f"  File exists: {exists}")
        except Exception as e:
            print(f"  Error checking file: {e}")
    else:
        print(f"  No image")

# Проверка того, что вернется в контексте
print("\n=== Что будет в контексте HomeView ===")
active_promos = Promotion.objects.filter(is_active=True).order_by('order', '-created_at')
print(f"Количество активных акций для шаблона: {active_promos.count()}")
for p in active_promos:
    print(f"  - {p.title or f'Акция #{p.id}'}")
PYEOF

echo ""
echo "=== Проверка настроек медиа ==="
python manage.py shell << 'PYEOF'
from django.conf import settings
print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"STATIC_URL: {settings.STATIC_URL}")
PYEOF
