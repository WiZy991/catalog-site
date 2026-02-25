"""
Management команда для автоматического обновления прайс-листа на Farpost.

Использование:
    python manage.py update_farpost_price_list
    
Проверяет все активные настройки Farpost с включенным автоматическим обновлением
и обновляет прайс-листы по расписанию.

Можно запускать по расписанию через cron:
    # Обновление каждый час
    0 * * * * cd /path/to/project && python manage.py update_farpost_price_list
"""
import os
import logging
import requests
import hashlib
import tempfile
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from catalog.models import FarpostAPISettings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Автоматически обновляет прайс-листы на Farpost по расписанию'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить все активные настройки, игнорируя интервал',
        )
        parser.add_argument(
            '--settings-id',
            type=int,
            help='Обновить только конкретные настройки по ID',
        )

    def handle(self, *args, **options):
        self.stdout.write('Проверка настроек автоматического обновления Farpost...')
        
        # Получаем настройки для обновления
        queryset = FarpostAPISettings.objects.filter(
            is_active=True,
            auto_update_enabled=True
        )
        
        if options['settings_id']:
            queryset = queryset.filter(pk=options['settings_id'])
        
        if not queryset.exists():
            self.stdout.write(self.style.WARNING('Нет активных настроек с включенным автоматическим обновлением'))
            return
        
        self.stdout.write(f'Найдено настроек: {queryset.count()}')
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for settings in queryset:
            self.stdout.write('')
            self.stdout.write(f'Обработка настроек: {settings} (ID: {settings.pk})')
            
            # Проверяем, нужно ли обновлять
            if not options['force']:
                if settings.last_auto_update:
                    # Проверяем интервал
                    time_since_update = timezone.now() - settings.last_auto_update
                    hours_since_update = time_since_update.total_seconds() / 3600
                    
                    if hours_since_update < settings.auto_update_interval:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Пропуск: последнее обновление было {hours_since_update:.1f} часов назад, '
                                f'интервал: {settings.auto_update_interval} часов'
                            )
                        )
                        skipped_count += 1
                        continue
            
            # Проверяем наличие URL
            if not settings.auto_update_url:
                self.stdout.write(
                    self.style.ERROR('  Ошибка: не указана ссылка на прайс-лист (auto_update_url)')
                )
                error_count += 1
                continue
            
            # Загружаем прайс-лист
            self.stdout.write(f'  Загрузка прайс-листа: {settings.auto_update_url}')
            try:
                response = requests.get(settings.auto_update_url, timeout=60)
                response.raise_for_status()
                
                # Определяем формат файла по расширению или Content-Type
                file_format = self._detect_file_format(settings.auto_update_url, response)
                self.stdout.write(f'  Определен формат: {file_format}')
                
                # Проверяем размер файла (лимит 5 МБ)
                file_size = len(response.content)
                file_size_mb = file_size / (1024 * 1024)
                self.stdout.write(f'  Размер файла: {file_size_mb:.2f} MB')
                
                if file_size_mb > 5:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  Ошибка: размер файла ({file_size_mb:.2f} MB) превышает лимит API Farpost (5 MB)'
                        )
                    )
                    error_count += 1
                    settings.last_auto_update = timezone.now()
                    settings.last_sync_status = 'error'
                    settings.last_sync_error = f'Размер файла превышает лимит: {file_size_mb:.2f} MB > 5 MB'
                    settings.save()
                    continue
                
                # Отправляем на Farpost API
                self.stdout.write('  Отправка на API Farpost...')
                success, message = self._send_to_farpost_api(
                    settings, 
                    response.content, 
                    file_format
                )
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {message}'))
                    settings.last_auto_update = timezone.now()
                    settings.last_sync = timezone.now()
                    settings.last_sync_status = 'success'
                    settings.last_sync_error = ''
                    settings.save()
                    updated_count += 1
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ {message}'))
                    settings.last_auto_update = timezone.now()
                    settings.last_sync = timezone.now()
                    settings.last_sync_status = 'error'
                    settings.last_sync_error = message
                    settings.save()
                    error_count += 1
                    
            except requests.exceptions.RequestException as e:
                error_msg = f'Ошибка при загрузке прайс-листа: {str(e)}'
                self.stdout.write(self.style.ERROR(f'  ✗ {error_msg}'))
                logger.error(f'Ошибка загрузки прайс-листа для настроек {settings.pk}: {e}')
                settings.last_auto_update = timezone.now()
                settings.last_sync_status = 'error'
                settings.last_sync_error = error_msg
                settings.save()
                error_count += 1
            except Exception as e:
                error_msg = f'Неожиданная ошибка: {str(e)}'
                self.stdout.write(self.style.ERROR(f'  ✗ {error_msg}'))
                logger.error(f'Неожиданная ошибка для настроек {settings.pk}: {e}', exc_info=True)
                settings.last_auto_update = timezone.now()
                settings.last_sync_status = 'error'
                settings.last_sync_error = error_msg
                settings.save()
                error_count += 1
        
        # Итоговая статистика
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Обновлено: {updated_count}')
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Пропущено: {skipped_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Ошибок: {error_count}'))
        self.stdout.write('=' * 60)
    
    def _detect_file_format(self, url, response):
        """Определяет формат файла по URL и Content-Type."""
        # По расширению в URL
        url_lower = url.lower()
        if url_lower.endswith('.xml'):
            return 'xml'
        elif url_lower.endswith('.csv'):
            return 'csv'
        elif url_lower.endswith('.xls') or url_lower.endswith('.xlsx'):
            return 'xls'
        
        # По Content-Type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'xml' in content_type:
            return 'xml'
        elif 'csv' in content_type or 'text/csv' in content_type:
            return 'csv'
        elif 'excel' in content_type or 'spreadsheet' in content_type:
            return 'xls'
        
        # По умолчанию CSV
        return 'csv'
    
    def _send_to_farpost_api(self, settings, file_content, file_format):
        """
        Отправляет файл на API Farpost.
        
        Возвращает: (success: bool, message: str)
        """
        try:
            # Получаем хеш для аутентификации
            auth_hash = settings.get_auth_hash()
            
            # Определяем имя файла и content-type
            filename = f'price_list_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            if file_format == 'xml':
                filename += '.xml'
                content_type = 'application/xml; charset=utf-8'
            elif file_format == 'csv':
                filename += '.csv'
                content_type = 'text/csv; charset=utf-8'
            else:  # xls
                filename += '.xls'
                content_type = 'application/vnd.ms-excel'
            
            # Подготавливаем данные для отправки
            files = {
                'data': (filename, file_content, content_type)
            }
            
            data = {
                'packetId': settings.packet_id,
                'auth': auth_hash
            }
            
            # Отправляем запрос
            api_url = 'https://www.farpost.ru/good/packet/api/sync'
            
            # Таймаут зависит от размера файла
            file_size_mb = len(file_content) / (1024 * 1024)
            timeout = max(60, int(file_size_mb * 20) + 30)  # Примерно 20 сек на МБ, минимум 60
            
            response = requests.post(
                api_url,
                data=data,
                files=files,
                timeout=timeout
            )
            
            if response.status_code == 200:
                return True, 'Прайс-лист успешно обновлен на Farpost'
            else:
                error_text = response.text[:500] if hasattr(response, 'text') else ''
                return False, f'Ошибка API Farpost: {response.status_code} - {error_text}'
                
        except requests.exceptions.RequestException as e:
            return False, f'Ошибка при отправке запроса к API Farpost: {str(e)}'
        except Exception as e:
            return False, f'Неожиданная ошибка: {str(e)}'
