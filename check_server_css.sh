#!/bin/bash
# Скрипт для проверки стилей на сервере

cd ~/onesimus/onesimus

echo "=== Проверка стилей корзины ==="
echo "Проверка aspect-ratio:"
grep -n "aspect-ratio.*1 / 1" static/css/style.css
grep -n "aspect-ratio.*1 / 1" static/css/cart.css

echo ""
echo "=== Проверка стилей категорий ==="
echo "Проверка border-radius для category-card__icon:"
grep -A 2 "\.category-card__icon {" static/css/style.css | grep "border-radius"

echo ""
echo "Проверка border-radius для catalog-category__icon:"
grep -A 2 "\.catalog-category__icon {" static/css/style.css | grep "border-radius"

echo ""
echo "=== Проверка карусели акций ==="
echo "CSS стили:"
grep -c "promotions-carousel" static/css/style.css

echo ""
echo "JavaScript:"
grep -c "initPromotionsCarousel" static/js/main.js

echo ""
echo "=== Размеры файлов ==="
wc -l static/css/style.css static/css/cart.css static/js/main.js
