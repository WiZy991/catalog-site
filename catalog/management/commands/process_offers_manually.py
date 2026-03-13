"""
Команда для ручной обработки файла offers.xml.
Используется, если файл не был обработан автоматически при обмене.
"""
from django.core.management.base import BaseCommand
from catalog.commerceml_views import process_commerceml_file
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Ручная обработка файла offers.xml'

    def add_arguments(self, parser):
        parser.add_argument(
            'filename',
            type=str,
            help='Имя файла offers.xml для обработки (например, offers0_1 или offers0_1.xml)',
        )

    def handle(self, *args, **options):
        filename = options['filename']
        
        self.stdout.write("=" * 80)
        self.stdout.write("РУЧНАЯ ОБРАБОТКА ФАЙЛА OFFERS")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        # Определяем путь к файлу
        exchange_dir = getattr(settings, 'ONE_C_EXCHANGE_DIR', os.path.join(settings.MEDIA_ROOT, '1c_exchange'))
        
        # Пробуем разные варианты имени файла
        possible_paths = [
            os.path.join(exchange_dir, filename),
            os.path.join(exchange_dir, filename + '.xml'),
            os.path.join(exchange_dir, filename.replace('.xml', '')),
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            self.stdout.write(self.style.ERROR(f"Файл не найден: {filename}"))
            self.stdout.write(f"Искали в: {exchange_dir}")
            self.stdout.write(f"Пробовали пути:")
            for path in possible_paths:
                self.stdout.write(f"  - {path}")
            return
        
        self.stdout.write(f"Найден файл: {file_path}")
        self.stdout.write(f"Размер файла: {os.path.getsize(file_path)} байт")
        self.stdout.write()
        
        # Обрабатываем файл
        self.stdout.write("Начинаем обработку...")
        self.stdout.write()
        
        try:
            result = process_commerceml_file(file_path, filename, request=None)
            
            self.stdout.write()
            self.stdout.write("=" * 80)
            self.stdout.write("РЕЗУЛЬТАТ ОБРАБОТКИ")
            self.stdout.write("=" * 80)
            self.stdout.write()
            
            if result.get('status') == 'success':
                self.stdout.write(self.style.SUCCESS("✓ Обработка завершена успешно"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠ Обработка завершена с предупреждениями: {result.get('status')}"))
            
            self.stdout.write(f"Обработано товаров: {result.get('processed', 0)}")
            self.stdout.write(f"Обновлено товаров: {result.get('updated', 0)}")
            
            errors = result.get('errors', [])
            if errors:
                self.stdout.write()
                self.stdout.write(self.style.ERROR("Ошибки:"))
                # Проверяем, что errors - это список
                if isinstance(errors, list):
                    for error in errors[:10]:
                        self.stdout.write(f"  - {error}")
                else:
                    self.stdout.write(f"  - {errors}")
            
            self.stdout.write()
            self.stdout.write("Проверьте результат:")
            self.stdout.write("  python manage.py check_products_status")
            
        except Exception as e:
            self.stdout.write()
            self.stdout.write(self.style.ERROR(f"Ошибка при обработке файла: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write()
        self.stdout.write("=" * 80)
