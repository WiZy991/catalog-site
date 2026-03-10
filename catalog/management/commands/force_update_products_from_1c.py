"""
Management команда для принудительного обновления всех товаров из XML файла 1С.

Использование:
    python manage.py force_update_products_from_1c --file import.xml
    
    или
    
    python manage.py force_update_products_from_1c --all
    
Обновляет ВСЕ товары из указанного XML файла, даже если они уже были обработаны.
Использует ту же логику, что и обычный обмен, но принудительно обновляет все товары.
"""
import os
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from catalog.commerceml_views import EXCHANGE_DIR, process_commerceml_file

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Принудительно обновляет все товары из XML файла 1С'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Путь к XML файлу для обработки (относительно директории обмена или абсолютный путь)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Обработать все XML файлы в директории обмена',
        )
        parser.add_argument(
            '--catalog-type',
            type=str,
            choices=['retail', 'wholesale', 'both'],
            default='both',
            help='Тип каталога для обновления (retail, wholesale, both)',
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ТОВАРОВ ИЗ 1С'))
        self.stdout.write('=' * 80)
        
        # Проверяем, что директория существует
        if not os.path.exists(EXCHANGE_DIR):
            self.stdout.write(self.style.ERROR(f'Директория обмена не существует: {EXCHANGE_DIR}'))
            return
        
        files_to_process = []
        
        # Если указан конкретный файл
        if options['file']:
            file_path = options['file']
            # Если путь относительный, добавляем директорию обмена
            if not os.path.isabs(file_path):
                file_path = os.path.join(EXCHANGE_DIR, file_path)
            
            if not os.path.exists(file_path):
                self.stdout.write(self.style.ERROR(f'Файл не найден: {file_path}'))
                return
            
            files_to_process.append(file_path)
        
        # Если опция --all, обрабатываем все XML файлы
        elif options['all']:
            try:
                files = os.listdir(EXCHANGE_DIR)
                xml_files = [f for f in files if f.lower().endswith('.xml')]
                
                if not xml_files:
                    self.stdout.write(self.style.WARNING('XML файлы не найдены в директории обмена'))
                    return
                
                # Сортируем файлы: сначала import.xml, потом offers.xml
                def sort_key(filename):
                    filename_lower = filename.lower()
                    if 'import' in filename_lower and 'offers' not in filename_lower:
                        return (0, filename)
                    elif 'offers' in filename_lower:
                        return (1, filename)
                    else:
                        return (2, filename)
                
                xml_files = sorted(xml_files, key=sort_key)
                
                for filename in xml_files:
                    file_path = os.path.join(EXCHANGE_DIR, filename)
                    files_to_process.append(file_path)
                
                self.stdout.write(f'Найдено XML файлов: {len(files_to_process)}')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка чтения директории: {e}'))
                return
        
        else:
            self.stdout.write(self.style.ERROR('Укажите --file <путь_к_файлу> или --all для обработки всех файлов'))
            return
        
        # Обрабатываем файлы
        total_processed = 0
        total_created = 0
        total_updated = 0
        total_errors = 0
        
        for file_path in files_to_process:
            filename = os.path.basename(file_path)
            self.stdout.write('')
            self.stdout.write('-' * 80)
            self.stdout.write(f'Обработка файла: {filename}')
            self.stdout.write(f'Полный путь: {file_path}')
            
            try:
                # Показываем размер файла
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                self.stdout.write(f'Размер файла: {file_size_mb:.2f} MB')
                
                # Обрабатываем файл
                self.stdout.write('Начинаем обработку...')
                result = process_commerceml_file(file_path, filename)
                
                if result['status'] == 'success':
                    processed = result.get('processed', 0)
                    created = result.get('created', 0)
                    updated = result.get('updated', 0)
                    
                    total_processed += processed
                    total_created += created
                    total_updated += updated
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Файл обработан успешно!'
                    ))
                    self.stdout.write(f'  Обработано товаров: {processed}')
                    self.stdout.write(f'  Создано новых: {created}')
                    self.stdout.write(f'  Обновлено: {updated}')
                    
                elif result['status'] == 'partial':
                    processed = result.get('processed', 0)
                    created = result.get('created', 0)
                    updated = result.get('updated', 0)
                    
                    total_processed += processed
                    total_created += created
                    total_updated += updated
                    
                    self.stdout.write(self.style.WARNING(
                        f'⚠ Файл обработан частично'
                    ))
                    self.stdout.write(f'  Обработано товаров: {processed}')
                    self.stdout.write(f'  Создано новых: {created}')
                    self.stdout.write(f'  Обновлено: {updated}')
                    
                    if result.get('errors'):
                        self.stdout.write(self.style.ERROR(f'  Ошибки: {len(result["errors"])}'))
                        for error in result['errors'][:5]:  # Показываем первые 5 ошибок
                            self.stdout.write(f'    - {error}')
                        if len(result['errors']) > 5:
                            self.stdout.write(f'    ... и еще {len(result["errors"]) - 5} ошибок')
                
                else:
                    total_errors += 1
                    error_msg = result.get('error', 'Неизвестная ошибка')
                    self.stdout.write(self.style.ERROR(f'✗ Ошибка обработки: {error_msg}'))
                    logger.error(f'Ошибка обработки файла {filename}: {error_msg}')
                
            except Exception as e:
                total_errors += 1
                self.stdout.write(self.style.ERROR(f'✗ Исключение при обработке: {e}'))
                logger.error(f'Исключение при обработке файла {filename}: {e}', exc_info=True)
        
        # Итоговая статистика
        self.stdout.write('')
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('ИТОГОВАЯ СТАТИСТИКА'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Обработано файлов: {len(files_to_process)}')
        self.stdout.write(f'Всего обработано товаров: {total_processed}')
        self.stdout.write(self.style.SUCCESS(f'Создано новых товаров: {total_created}'))
        self.stdout.write(self.style.SUCCESS(f'Обновлено товаров: {total_updated}'))
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'Ошибок: {total_errors}'))
        self.stdout.write('=' * 80)
        self.stdout.write('')
        
        if total_updated > 0:
            self.stdout.write(self.style.SUCCESS(
                f'✓ Успешно обновлено {total_updated} товаров!'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                '⚠ Товары не были обновлены. Проверьте логи для диагностики.'
            ))
