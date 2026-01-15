#!/bin/bash
# Скрипт для проверки и исправления миграций на сервере

echo "=== Проверка миграций ==="
ls -la catalog/migrations/000*.py

echo ""
echo "=== Статус миграций в Django ==="
python manage.py showmigrations catalog

echo ""
echo "=== Проверка содержимого 0006_promotion.py ==="
grep -A 5 "dependencies" catalog/migrations/0006_promotion.py
