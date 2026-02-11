"""
Скрипт для диагностики обмена с 1С.
Проверяет логи синхронизации, файлы обмена и последние обмены.
"""
import os
import sys
from pathlib import Path

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from catalog.models import SyncLog, Product
from django.utils import timezone
from datetime import timedelta

def check_exchange_directory():
    """Проверяет директорию обмена с 1С."""
    exchange_dir = getattr(settings, 'ONE_C_EXCHANGE_DIR', None)
    if not exchange_dir:
        exchange_dir = os.path.join(settings.MEDIA_ROOT, '1c_exchange')
    
    print(f"\n{'='*80}")
    print("ПРОВЕРКА ДИРЕКТОРИИ ОБМЕНА")
    print(f"{'='*80}")
    print(f"Директория: {exchange_dir}")
    print(f"Существует: {os.path.exists(exchange_dir)}")
    
    if os.path.exists(exchange_dir):
        files = os.listdir(exchange_dir)
        print(f"Файлов в директории: {len(files)}")
        if files:
            print("\nПоследние 10 файлов:")
            # Сортируем по времени изменения
            files_with_time = []
            for f in files:
                file_path = os.path.join(exchange_dir, f)
                if os.path.isfile(file_path):
                    mtime = os.path.getmtime(file_path)
                    size = os.path.getsize(file_path)
                    files_with_time.append((f, mtime, size))
            
            files_with_time.sort(key=lambda x: x[1], reverse=True)
            for f, mtime, size in files_with_time[:10]:
                mtime_str = timezone.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  {f} ({size} байт, изменен: {mtime_str})")
        else:
            print("Директория пуста!")
    else:
        print("⚠️ Директория не существует! Файлы обмена не сохраняются.")

def check_sync_logs():
    """Проверяет логи синхронизации."""
    print(f"\n{'='*80}")
    print("ПРОВЕРКА ЛОГОВ СИНХРОНИЗАЦИИ")
    print(f"{'='*80}")
    
    # Последние 10 логов
    recent_logs = SyncLog.objects.all()[:10]
    print(f"Всего логов: {SyncLog.objects.count()}")
    print(f"\nПоследние 10 логов синхронизации:")
    
    if recent_logs:
        for log in recent_logs:
            print(f"\n  Лог #{log.id}:")
            print(f"    Тип: {log.get_operation_type_display()}")
            print(f"    Статус: {log.get_status_display()}")
            print(f"    Дата: {log.created_at}")
            print(f"    Обработано: {log.processed_count}")
            print(f"    Создано: {log.created_count}")
            print(f"    Обновлено: {log.updated_count}")
            print(f"    Ошибок: {log.errors_count}")
            if log.filename:
                print(f"    Файл: {log.filename}")
            if log.message:
                print(f"    Сообщение: {log.message[:100]}")
            if log.errors:
                print(f"    Ошибки: {log.errors[:3]}")  # Первые 3 ошибки
    else:
        print("⚠️ Логов синхронизации не найдено! Обмены не происходили или не логируются.")

def check_recent_products():
    """Проверяет последние добавленные/обновленные товары."""
    print(f"\n{'='*80}")
    print("ПРОВЕРКА ПОСЛЕДНИХ ТОВАРОВ")
    print(f"{'='*80}")
    
    # Товары с external_id (из 1С)
    products_with_external_id = Product.objects.exclude(external_id__isnull=True).exclude(external_id='')
    print(f"Товаров с external_id: {products_with_external_id.count()}")
    
    # Последние 10 товаров с external_id
    recent_products = products_with_external_id.order_by('-updated_at')[:10]
    if recent_products:
        print("\nПоследние 10 товаров с external_id:")
        for product in recent_products:
            print(f"  {product.article} - {product.name[:50]} (external_id: {product.external_id}, обновлен: {product.updated_at})")
    else:
        print("⚠️ Товаров с external_id не найдено!")

def check_settings():
    """Проверяет настройки обмена."""
    print(f"\n{'='*80}")
    print("ПРОВЕРКА НАСТРОЕК")
    print(f"{'='*80}")
    
    exchange_dir = getattr(settings, 'ONE_C_EXCHANGE_DIR', None)
    file_limit = getattr(settings, 'ONE_C_FILE_LIMIT', None)
    support_zip = getattr(settings, 'ONE_C_SUPPORT_ZIP', None)
    
    print(f"ONE_C_EXCHANGE_DIR: {exchange_dir}")
    print(f"ONE_C_FILE_LIMIT: {file_limit} байт ({file_limit / 1024 / 1024:.1f} MB)" if file_limit else "Не установлен")
    print(f"ONE_C_SUPPORT_ZIP: {support_zip}")
    
    # Проверяем URL
    print(f"\nОжидаемый URL для 1С:")
    print(f"  http://<ваш_сайт>/cml/exchange?type=catalog&mode=checkauth")
    print(f"\nАльтернативные URL:")
    print(f"  http://<ваш_сайт>/cml/exchange/?type=catalog&mode=checkauth")
    print(f"  http://<ваш_сайт>/1c_exchange.php?type=catalog&mode=checkauth")

def main():
    """Основная функция."""
    print("="*80)
    print("ДИАГНОСТИКА ОБМЕНА С 1С")
    print("="*80)
    
    check_settings()
    check_exchange_directory()
    check_sync_logs()
    check_recent_products()
    
    print(f"\n{'='*80}")
    print("РЕКОМЕНДАЦИИ")
    print(f"{'='*80}")
    print("1. Проверьте логи Django (logs/django.log) на наличие запросов от 1С")
    print("2. Убедитесь, что в 1С указан правильный URL: /cml/exchange/")
    print("3. Проверьте, что логин и пароль в 1С соответствуют пользователю Django с правами staff")
    print("4. Проверьте логи SyncLog в админ-панели Django")
    print("5. Если файлы сохраняются, но товары не создаются - проверьте ошибки в логах")
    print("="*80)

if __name__ == '__main__':
    main()
