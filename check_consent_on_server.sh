#!/bin/bash
# Скрипт для проверки страницы согласия на сервере

echo "=== Проверка страницы согласия на сервере ==="
echo ""

cd ~/onesimus/onesimus

echo "1. Проверка наличия URL в core/urls.py..."
if grep -q "path('consent/" core/urls.py; then
    echo "✓ URL найден"
else
    echo "✗ URL НЕ найден! Нужно обновить код."
fi

echo ""
echo "2. Проверка наличия view в core/views.py..."
if grep -q "class ConsentView" core/views.py; then
    echo "✓ View найден"
else
    echo "✗ View НЕ найден! Нужно обновить код."
fi

echo ""
echo "3. Проверка наличия шаблона..."
if [ -f "templates/core/consent.html" ]; then
    echo "✓ Шаблон найден"
else
    echo "✗ Шаблон НЕ найден! Нужно обновить код."
fi

echo ""
echo "4. Проверка namespace в core/urls.py..."
if grep -q "app_name = 'core'" core/urls.py; then
    echo "✓ Namespace настроен"
else
    echo "✗ Namespace НЕ настроен! Нужно обновить код."
fi

echo ""
echo "5. Проверка подключения core.urls в config/urls.py..."
if grep -q "include('core.urls')" config/urls.py; then
    echo "✓ core.urls подключен"
else
    echo "✗ core.urls НЕ подключен! Нужно обновить код."
fi

echo ""
echo "=== Решение ==="
echo "Если что-то не найдено, выполните:"
echo "  git pull origin main"
echo "  touch tmp/restart.txt"
