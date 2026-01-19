#!/bin/bash
# Проверка шаблона на сервере

cd ~/onesimus/onesimus

echo "=== Проверка шаблона order_create.html ==="
echo ""

# Проверьте строку 71 в шаблоне
echo "Строка 71 в templates/orders/order_create.html:"
sed -n '71p' templates/orders/order_create.html

echo ""
echo "Все использования consent в шаблоне:"
grep -n "consent" templates/orders/order_create.html

echo ""
echo "=== Проверка namespace в core/urls.py ==="
grep "app_name" core/urls.py

echo ""
echo "=== Проверка URL consent в core/urls.py ==="
grep "consent" core/urls.py
