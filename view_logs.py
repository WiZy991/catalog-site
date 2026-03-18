#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для просмотра логов Django
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / 'logs' / 'django.log'
COMMERCEML_LOG = BASE_DIR / 'logs' / 'commerceml_requests.log'

def view_logs(tail_lines=100, follow=False):
    """Просмотр логов Django"""
    
    if not LOG_FILE.exists():
        print(f"❌ Файл логов не найден: {LOG_FILE}")
        return
    
    print(f"📄 Просмотр логов из: {LOG_FILE}")
    print("=" * 80)
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            if tail_lines:
                lines = lines[-tail_lines:]
            
            for line in lines:
                print(line.rstrip())
            
            if follow:
                print("\n🔄 Режим отслеживания (Ctrl+C для выхода)...")
                import time
                while True:
                    new_lines = f.readlines()
                    for line in new_lines:
                        print(line.rstrip())
                    time.sleep(0.5)
                    
    except KeyboardInterrupt:
        print("\n\n✅ Просмотр завершен")
    except Exception as e:
        print(f"❌ Ошибка чтения логов: {e}")

def view_commerceml_logs(tail_lines=100):
    """Просмотр логов CommerceML"""
    
    if not COMMERCEML_LOG.exists():
        print(f"ℹ️ Файл логов CommerceML не найден: {COMMERCEML_LOG}")
        return
    
    print(f"📄 Просмотр логов CommerceML из: {COMMERCEML_LOG}")
    print("=" * 80)
    
    try:
        with open(COMMERCEML_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            if tail_lines:
                lines = lines[-tail_lines:]
            
            for line in lines:
                print(line.rstrip())
                    
    except Exception as e:
        print(f"❌ Ошибка чтения логов: {e}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Просмотр логов Django')
    parser.add_argument('-n', '--lines', type=int, default=100, help='Количество последних строк (по умолчанию 100)')
    parser.add_argument('-f', '--follow', action='store_true', help='Отслеживать новые записи в реальном времени')
    parser.add_argument('--commerceml', action='store_true', help='Показать логи CommerceML')
    
    args = parser.parse_args()
    
    if args.commerceml:
        view_commerceml_logs(args.lines)
    else:
        view_logs(args.lines, args.follow)
