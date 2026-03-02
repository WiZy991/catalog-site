#!/bin/bash
# Скрипт для исправления дубликата в category.html на сервере

cd ~/onesimus/onesimus

# Найти строку с последним {% endblock %} перед дубликатом
# Удалить все после строки 312 (после {% endblock %})

# Создаем резервную копию
cp templates/catalog/category.html templates/catalog/category.html.backup

# Удаляем все строки после 312-й (после {% endblock %})
# Оставляем только правильную часть файла
head -n 312 templates/catalog/category.html > templates/catalog/category.html.tmp
mv templates/catalog/category.html.tmp templates/catalog/category.html

# Проверяем, что остался только один блок title
echo "Проверка блоков title:"
grep -n "block title" templates/catalog/category.html

echo ""
echo "Файл исправлен! Проверьте результат."
