#!/bin/bash
# Скрипт для проверки наличия файлов восстановления пароля на сервере

echo "=== Проверка файлов восстановления пароля ==="
echo ""

echo "1. Проверка partners/urls.py:"
if grep -q "password_reset" partners/urls.py; then
    echo "   ✓ URL маршруты найдены"
    grep "password_reset" partners/urls.py
else
    echo "   ✗ URL маршруты НЕ найдены!"
fi
echo ""

echo "2. Проверка partners/views.py:"
if grep -q "PartnerPasswordResetView" partners/views.py; then
    echo "   ✓ Views найдены"
    grep -c "class PartnerPasswordReset" partners/views.py | xargs echo "   Количество views:"
else
    echo "   ✗ Views НЕ найдены!"
fi
echo ""

echo "3. Проверка partners/forms.py:"
if grep -q "PartnerPasswordResetForm" partners/forms.py; then
    echo "   ✓ Формы найдены"
    grep -c "class PartnerPasswordReset\|class PartnerSetPassword" partners/forms.py | xargs echo "   Количество форм:"
else
    echo "   ✗ Формы НЕ найдены!"
fi
echo ""

echo "4. Проверка шаблонов:"
TEMPLATES=(
    "templates/partners/password_reset.html"
    "templates/partners/password_reset_done.html"
    "templates/partners/password_reset_confirm.html"
    "templates/partners/password_reset_complete.html"
    "templates/partners/password_reset_email.html"
    "templates/partners/password_reset_subject.txt"
)

for template in "${TEMPLATES[@]}"; do
    if [ -f "$template" ]; then
        echo "   ✓ $template"
    else
        echo "   ✗ $template - НЕ НАЙДЕН!"
    fi
done
echo ""

echo "=== Проверка завершена ==="
