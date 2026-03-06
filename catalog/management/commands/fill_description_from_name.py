"""
Заполняет поле description у товаров (розничных и оптовых) из названия товара.
Извлекает модели из скобок в названии и формирует "Кузов: ...".
"""
from django.core.management.base import BaseCommand
from django.db import models
from catalog.models import Product
import re


class Command(BaseCommand):
    help = 'Заполняет поле description у товаров из названия'

    def add_arguments(self, parser):
        parser.add_argument(
            '--catalog-type',
            choices=['retail', 'wholesale', 'both'],
            default='both',
            help='Тип каталога для обработки (по умолчанию: both)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет изменено, без фактического изменения',
        )

    def extract_models_from_name(self, name):
        """Извлекает модели из названия товара."""
        models_list = []
        # Ищем паттерны в скобках: "HZJ70/HZJ80" или "2UZFE/1GRFE" или "M300/M301"
        bracket_matches = re.findall(r'\(([^)]+)\)', name)
        for bracket_content in bracket_matches:
            parts = [p.strip() for p in bracket_content.split(',')]
            for part in parts:
                # Пропускаем артикулы (типа 43530-60042)
                if re.match(r'^\d{5}-\d{5}$', part) or re.match(r'^\d{1}-\d{5}-\d{3}-\d{1}$', part) or re.match(r'^\d{5}-\d{3}$', part):
                    continue
                # Пропускаем бренды (TOYOTA, HONDA и т.д.)
                if part.upper() in ['TOYOTA', 'HONDA', 'DAIHATSU', 'NISSAN', 'MAZDA', 'MITSUBISHI', 'SUBARU', 'ISUZU', 'SUZUKI']:
                    continue
                # Если это похоже на модель (содержит буквы и цифры, разделенные /)
                if '/' in part and re.search(r'[A-Za-z]', part):
                    models_list.append(part.strip())
                elif re.search(r'[A-Za-z]', part) and not re.match(r'^\d+$', part) and len(part) > 2:
                    models_list.append(part.strip())
        
        return models_list

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']
        
        # Определяем, какие каталоги обрабатывать
        if catalog_type == 'both':
            catalog_types = ['retail', 'wholesale']
        else:
            catalog_types = [catalog_type]
        
        total_updated = 0
        total_skipped = 0
        
        for current_catalog_type in catalog_types:
            self.stdout.write(f'\nОбработка каталога: {current_catalog_type}')
            self.stdout.write('=' * 60)
            
            # Находим товары без description или с пустым description
            products = Product.objects.filter(
                catalog_type=current_catalog_type
            ).filter(
                models.Q(description__isnull=True) | models.Q(description='')
            )
            
            updated_count = 0
            skipped_count = 0
            
            for product in products:
                models_list = self.extract_models_from_name(product.name)
                
                if models_list:
                    # Формируем description из моделей
                    description_parts = []
                    for model in models_list[:3]:  # Берем первые 3 модели
                        description_parts.append(f"Кузов: {model}")
                    
                    new_description = '\n'.join(description_parts)
                    
                    if dry_run:
                        self.stdout.write(
                            f'[DRY RUN] Будет обновлено описание у товара "{product.name}" '
                            f'(ID: {product.pk}): {new_description}'
                        )
                    else:
                        product.description = new_description
                        product.save(update_fields=['description'])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Обновлено описание у товара "{product.name}" (ID: {product.pk})'
                            )
                        )
                    updated_count += 1
                else:
                    skipped_count += 1
            
            total_updated += updated_count
            total_skipped += skipped_count
            
            self.stdout.write(f'Обновлено: {updated_count}, пропущено: {skipped_count}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Всего будет обновлено описаний: {total_updated}, '
                    f'пропущено: {total_skipped}'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Запустите команду без --dry-run для фактического обновления'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Готово! Всего обновлено описаний: {total_updated}, пропущено: {total_skipped}'
                )
            )
