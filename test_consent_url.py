#!/usr/bin/env python
"""
Скрипт для проверки URL согласия
Запустите: python test_consent_url.py
"""
import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.urls import reverse
from core.views import ConsentView

print("=== Проверка URL согласия ===\n")

# Проверка разрешения URL
try:
    url = reverse('core:consent')
    print(f"✓ URL найден: {url}")
    print(f"  Полный URL: http://onesim8n.beget.tech{url}")
except Exception as e:
    print(f"✗ Ошибка разрешения URL: {e}")
    print(f"  Тип ошибки: {type(e).__name__}")

# Проверка импорта view
try:
    print(f"\n✓ ConsentView импортирован: {ConsentView}")
    print(f"  Template: {ConsentView.template_name}")
except Exception as e:
    print(f"\n✗ Ошибка импорта: {e}")

# Проверка существования шаблона
from django.template.loader import get_template
try:
    template = get_template('core/consent.html')
    print(f"\n✓ Шаблон найден: {template.origin}")
except Exception as e:
    print(f"\n✗ Ошибка загрузки шаблона: {e}")

print("\n=== Проверка завершена ===")
