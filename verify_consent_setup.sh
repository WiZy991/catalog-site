#!/bin/bash
# Скрипт для проверки настройки страницы согласия на сервере

echo "=== Проверка настройки страницы согласия ==="
echo ""

cd ~/onesimus/onesimus

echo "1. Проверка URL в core/urls.py..."
echo "---"
if grep -A 2 "consent" core/urls.py; then
    echo "✓ URL найден"
else
    echo "✗ URL НЕ найден!"
fi

echo ""
echo "2. Проверка namespace в core/urls.py..."
echo "---"
if grep "app_name" core/urls.py; then
    echo "✓ Namespace настроен"
else
    echo "✗ Namespace НЕ настроен!"
fi

echo ""
echo "3. Проверка view в core/views.py..."
echo "---"
if grep -A 3 "class ConsentView" core/views.py; then
    echo "✓ View найден"
else
    echo "✗ View НЕ найден!"
fi

echo ""
echo "4. Проверка подключения core.urls в config/urls.py..."
echo "---"
if grep "include('core.urls')" config/urls.py; then
    echo "✓ core.urls подключен"
else
    echo "✗ core.urls НЕ подключен!"
fi

echo ""
echo "5. Проверка шаблона..."
echo "---"
if [ -f "templates/core/consent.html" ]; then
    echo "✓ Шаблон существует"
    echo "Размер файла: $(ls -lh templates/core/consent.html | awk '{print $5}')"
else
    echo "✗ Шаблон НЕ существует!"
fi

echo ""
echo "=== Следующие шаги ==="
echo "Если все проверки пройдены, выполните:"
echo "  touch tmp/restart.txt"
echo ""
echo "Затем проверьте в браузере:"
echo "  http://onesim8n.beget.tech/consent/"
