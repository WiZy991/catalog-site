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
from django.core.management import call_command
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
        
        # ВАЖНО: Сортируем файлы так, чтобы сначала обрабатывались import.xml, потом offers.xml
        # Это гарантирует, что товары сначала создаются/обновляются, а потом обновляются цены и остатки
        def sort_key(filename):
            filename_lower = filename.lower()
            if 'import' in filename_lower and 'offers' not in filename_lower:
                return (0, filename)  # import.xml - приоритет 0 (обрабатываем первыми)
            elif 'offers' in filename_lower:
                return (1, filename)  # offers.xml - приоритет 1 (обрабатываем вторыми)
            else:
                return (2, filename)  # остальные файлы - приоритет 2
        
        target_files = sorted(target_files, key=sort_key)
        
        # Определяем время для фильтрации недавних файлов
        recent_minutes = options.get('recent', 0)
        cutoff_time = None
        if recent_minutes > 0:
            cutoff_time = datetime.now() - timedelta(minutes=recent_minutes)
            self.stdout.write(f'Обрабатываем файлы, измененные за последние {recent_minutes} минут')
        
        # ВАЖНО:
        # Не очищаем товары заранее. Иначе возможен сценарий:
        # 1) очистили товары
        # 2) все файлы пропущены по маркерам/фильтрам
        # => на сайте 0 товаров.
        # Очищаем только перед фактической обработкой ПЕРВОГО файла.
        cleared_before_processing = False

        for filename in target_files:  # Обрабатываем в правильном порядке
            file_path = os.path.join(EXCHANGE_DIR, filename)
            
            # ВАЖНО: Проверяем, не обработан ли уже файл (по наличию файла .processed)
            # И НЕ обрабатываем повторно, если файл не изменился (даже с --all)
            processed_marker = f"{file_path}.processed"
            if os.path.exists(processed_marker):
                # Файл уже обрабатывался - проверяем, изменился ли он
                try:
                    # Получаем текущее время файла
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    # Пытаемся прочитать время файла из маркера (если оно там сохранено)
                    file_mtime_from_marker = None
                    try:
                        with open(processed_marker, 'r') as f:
                            for line in f:
                                if line.startswith('file_mtime:'):
                                    file_mtime_from_marker = datetime.fromisoformat(line.split(':', 1)[1].strip())
                                    break
                    except Exception:
                        pass
                    
                    # Если время файла сохранено в маркере, используем его
                    # Иначе используем время маркера (старая логика)
                    if file_mtime_from_marker:
                        # Сравниваем текущее время файла с временем из маркера
                        if file_mtime <= file_mtime_from_marker:
                            self.stdout.write(f'Пропускаем файл (не изменился): {filename} (обработан {file_mtime_from_marker.strftime("%Y-%m-%d %H:%M:%S")}, текущее {file_mtime.strftime("%Y-%m-%d %H:%M:%S")})')
                            continue
                    else:
                        # Старая логика - сравниваем с временем маркера
                        marker_mtime = datetime.fromtimestamp(os.path.getmtime(processed_marker))
                        if file_mtime <= marker_mtime:
                            self.stdout.write(f'Пропускаем файл (не изменился): {filename} (маркер {marker_mtime.strftime("%Y-%m-%d %H:%M:%S")}, файл {file_mtime.strftime("%Y-%m-%d %H:%M:%S")})')
                            continue
                    
                    # Файл изменился - обрабатываем снова ТОЛЬКО если явно указано --all
                    # ВАЖНО: Для крона (без --all) НЕ обрабатываем файлы повторно, даже если они изменились
                    # Это предотвращает постоянную обработку файлов и изменения количества товаров
                    if options['all']:
                        if recent_minutes > 0 and file_mtime < cutoff_time:
                            self.stdout.write(f'Пропускаем старый файл: {filename} (изменен {file_mtime.strftime("%Y-%m-%d %H:%M:%S")})')
                            continue
                        self.stdout.write(f'Файл изменен после обработки, обрабатываем снова (--all): {filename}')
                    elif recent_minutes > 0:
                        # Если указан --recent, обрабатываем только недавно измененные файлы
                        if file_mtime < cutoff_time:
                            self.stdout.write(f'Пропускаем старый файл: {filename} (изменен {file_mtime.strftime("%Y-%m-%d %H:%M:%S")})')
                            continue
                        self.stdout.write(f'Файл изменен недавно, обрабатываем снова (--recent): {filename}')
                    else:
                        # Без --all и --recent пропускаем измененные файлы (для безопасности и производительности)
                        # Это предотвращает постоянную обработку файлов в кроне
                        self.stdout.write(f'Пропускаем уже обработанный файл (используйте --all для повторной обработки): {filename}')
                        continue
                except Exception as e:
                    # Если не удалось проверить время - пропускаем для безопасности
                    self.stdout.write(self.style.WARNING(f'Не удалось проверить время изменения файла {filename}: {e}, пропускаем'))
                    continue
            
            # Проверяем время модификации файла (если опция --recent включена)
            if recent_minutes > 0 and cutoff_time:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < cutoff_time:
                    self.stdout.write(f'Пропускаем старый файл: {filename} (изменен {file_mtime.strftime("%Y-%m-%d %H:%M:%S")})')
                    continue
            
            # ВАЖНО:
            # Товары создаются из offers.xml (import.xml только парсится/логируется),
            # поэтому очищаем 1С-товары только перед ПЕРВЫМ фактически обрабатываемым offers-файлом.
            is_offers_file = 'offers' in filename.lower()
            if is_offers_file and not cleared_before_processing:
                self.stdout.write(self.style.WARNING(
                    'Очищаем товары из 1С перед обработкой первого offers-файла: clear_1c_products --catalog-type all --yes'
                ))
                try:
                    from django.core.management import call_command
                    call_command('clear_1c_products', catalog_type='all', yes=True)
                    cleared_before_processing = True
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Ошибка очистки 1С-товаров: {e}'))
                    return

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
                    # ВАЖНО: Сохраняем время изменения ФАЙЛА, а не время создания маркера
                    # Это нужно для правильной проверки, изменился ли файл
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        file_mtime_iso = datetime.fromtimestamp(file_mtime).isoformat()
                        with open(processed_marker, 'w') as f:
                            f.write(f'processed\n')
                            f.write(f'file_mtime: {file_mtime_iso}\n')  # Время изменения файла
                            f.write(f'marker_time: {datetime.now().isoformat()}\n')  # Время создания маркера
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
