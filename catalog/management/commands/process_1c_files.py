"""
Management команда для автоматической обработки файлов от 1С.

Использование:
    python manage.py process_1c_files
    
Обрабатывает все необработанные XML файлы в директории обмена с 1С.
Можно запускать по расписанию через cron.

Автоматически обрабатывает файлы, которые:
- Имеют расширение .xml или .zip
- Не имеют маркера .processed
- Или были изменены недавно (опция --recent)
"""
import os
import logging
import time
from datetime import datetime, timedelta
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
        parser.add_argument(
            '--recent',
            type=int,
            default=0,
            help='Обработать только файлы, измененные за последние N минут (0 = все новые)',
        )
        parser.add_argument(
            '--zip',
            action='store_true',
            help='Обрабатывать также ZIP архивы',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Удалить маркеры обработанных файлов и обработать заново',
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
        
        # Если опция --reset, удаляем все маркеры .processed
        if options['reset']:
            self.stdout.write('Удаление маркеров обработанных файлов...')
            try:
                files = os.listdir(EXCHANGE_DIR)
                removed_count = 0
                for filename in files:
                    if filename.endswith('.processed'):
                        marker_path = os.path.join(EXCHANGE_DIR, filename)
                        try:
                            os.remove(marker_path)
                            removed_count += 1
                            self.stdout.write(f'  Удален маркер: {filename}')
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f'  Не удалось удалить {filename}: {e}'))
                self.stdout.write(self.style.SUCCESS(f'Удалено маркеров: {removed_count}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка при удалении маркеров: {e}'))
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
        
        # Фильтруем файлы (XML и опционально ZIP)
        file_extensions = ['.xml']
        if options['zip']:
            file_extensions.append('.zip')
        
        target_files = [f for f in files if any(f.lower().endswith(ext) for ext in file_extensions)]
        
        if not target_files:
            self.stdout.write(f'Файлы ({", ".join(file_extensions)}) не найдены в директории обмена')
            return
        
        self.stdout.write(f'Найдено файлов: {len(target_files)}')
        
        # Определяем время для фильтрации недавних файлов
        recent_minutes = options.get('recent', 0)
        cutoff_time = None
        if recent_minutes > 0:
            cutoff_time = datetime.now() - timedelta(minutes=recent_minutes)
            self.stdout.write(f'Обрабатываем файлы, измененные за последние {recent_minutes} минут')
        
        for filename in sorted(target_files):  # Сортируем по имени для предсказуемости
            file_path = os.path.join(EXCHANGE_DIR, filename)
            
            # Проверяем, не обработан ли уже файл (по наличию файла .processed)
            processed_marker = f"{file_path}.processed"
            if not options['all'] and os.path.exists(processed_marker):
                # Если файл уже обработан, но опция --recent включена, проверяем время модификации маркера
                if recent_minutes > 0:
                    marker_mtime = datetime.fromtimestamp(os.path.getmtime(processed_marker))
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    # Если файл был изменен после обработки, обрабатываем снова
                    if file_mtime > marker_mtime and file_mtime > cutoff_time:
                        self.stdout.write(f'Файл изменен после обработки, обрабатываем снова: {filename}')
                    else:
                        self.stdout.write(f'Пропускаем уже обработанный файл: {filename}')
                        continue
                else:
                    self.stdout.write(f'Пропускаем уже обработанный файл: {filename}')
                    continue
            
            # Проверяем время модификации файла (если опция --recent включена)
            if recent_minutes > 0 and cutoff_time:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < cutoff_time:
                    self.stdout.write(f'Пропускаем старый файл: {filename} (изменен {file_mtime.strftime("%Y-%m-%d %H:%M:%S")})')
                    continue
            
            self.stdout.write(f'Обработка файла: {filename}...')
            
            try:
                # Показываем размер файла
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                self.stdout.write(f'  Размер файла: {file_size_mb:.2f} MB')
                
                result = process_commerceml_file(file_path, filename)
                
                # ВАЖНО: Маркер создается только если товары действительно обработаны
                # Если processed_count = 0, это ошибка, маркер не создается
                processed_items = result.get("processed", 0)
                if result['status'] == 'success' and processed_items > 0:
                    processed_count += 1
                    # Создаем маркер обработанного файла
                    try:
                        with open(processed_marker, 'w') as f:
                            f.write(f'processed\n')
                            f.write(f'time: {datetime.now().isoformat()}\n')
                            f.write(f'processed_count: {processed_items}\n')
                            f.write(f'created: {result.get("created", 0)}\n')
                            f.write(f'updated: {result.get("updated", 0)}\n')
                    except Exception as marker_error:
                        self.stdout.write(self.style.WARNING(f'Не удалось создать маркер: {marker_error}'))
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ {filename}: обработано {processed_items} товаров '
                        f'(создано: {result.get("created", 0)}, обновлено: {result.get("updated", 0)})'
                    ))
                else:
                    error_count += 1
                    if processed_items == 0:
                        error_msg = f"Товары не обработаны (processed_count=0). Статус: {result.get('status', 'unknown')}"
                    else:
                        error_msg = result.get("error", "Неизвестная ошибка")
                    self.stdout.write(self.style.ERROR(f'✗ {filename}: {error_msg}'))
                    logger.error(f'Ошибка обработки файла {filename}: {error_msg}')
                    # НЕ создаем маркер, если товары не обработаны
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
