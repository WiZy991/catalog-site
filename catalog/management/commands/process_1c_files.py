"""
Management команда для автоматической обработки файлов от 1С.

Использование:
    python manage.py process_1c_files
    
Обрабатывает все необработанные XML файлы в директории обмена с 1С.
Можно запускать по расписанию через cron.
"""
import os
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from catalog.commerceml_views import EXCHANGE_DIR, process_commerceml_file

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обрабатывает все XML файлы от 1С в директории обмена'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Обработать все файлы, даже если они уже обработаны',
        )
        parser.add_argument(
            '--file',
            type=str,
            help='Обработать конкретный файл',
        )

    def handle(self, *args, **options):
        self.stdout.write('Начинаем обработку файлов от 1С...')
        
        # Проверяем, что директория существует
        if not os.path.exists(EXCHANGE_DIR):
            self.stdout.write(self.style.ERROR(f'Директория обмена не существует: {EXCHANGE_DIR}'))
            return
        
        # Если указан конкретный файл
        if options['file']:
            file_path = os.path.join(EXCHANGE_DIR, options['file'])
            if not os.path.exists(file_path):
                self.stdout.write(self.style.ERROR(f'Файл не найден: {file_path}'))
                return
            
            self.stdout.write(f'Обработка файла: {options["file"]}')
            try:
                result = process_commerceml_file(file_path, options['file'])
                if result['status'] == 'success':
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Файл обработан: обработано {result.get("processed", 0)} товаров'
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'✗ Ошибка обработки: {result.get("error", "Неизвестная ошибка")}'
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Исключение: {e}'))
            return
        
        # Обрабатываем все XML файлы в директории
        processed_count = 0
        error_count = 0
        
        # Получаем список файлов
        try:
            files = os.listdir(EXCHANGE_DIR)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка чтения директории: {e}'))
            return
        
        # Фильтруем XML файлы
        xml_files = [f for f in files if f.lower().endswith('.xml')]
        
        if not xml_files:
            self.stdout.write('XML файлы не найдены в директории обмена')
            return
        
        self.stdout.write(f'Найдено XML файлов: {len(xml_files)}')
        
        for filename in xml_files:
            file_path = os.path.join(EXCHANGE_DIR, filename)
            
            # Проверяем, не обработан ли уже файл (по наличию файла .processed)
            processed_marker = f"{file_path}.processed"
            if not options['all'] and os.path.exists(processed_marker):
                self.stdout.write(f'Пропускаем уже обработанный файл: {filename}')
                continue
            
            self.stdout.write(f'Обработка файла: {filename}...')
            
            try:
                result = process_commerceml_file(file_path, filename)
                
                if result['status'] == 'success':
                    processed_count += 1
                    # Создаем маркер обработанного файла
                    with open(processed_marker, 'w') as f:
                        f.write('processed')
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ {filename}: обработано {result.get("processed", 0)} товаров '
                        f'(создано: {result.get("created", 0)}, обновлено: {result.get("updated", 0)})'
                    ))
                else:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'✗ {filename}: {result.get("error", "Неизвестная ошибка")}'
                    ))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'✗ {filename}: исключение - {e}'))
                logger.error(f'Ошибка обработки файла {filename}: {e}', exc_info=True)
        
        # Итоговая статистика
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Обработано файлов: {processed_count}')
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Ошибок: {error_count}'))
        self.stdout.write('=' * 60)
