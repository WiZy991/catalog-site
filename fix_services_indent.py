#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Исправление отступов в catalog/services.py
"""

with open('catalog/services.py', 'rb') as f:
    content = f.read()

# Заменяем все табы на 4 пробела
content = content.replace(b'\t', b'    ')

# Записываем обратно
with open('catalog/services.py', 'wb') as f:
    f.write(content)

print("Готово! Все табы заменены на пробелы.")
