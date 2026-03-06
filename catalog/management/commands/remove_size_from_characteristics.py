from django.core.management.base import BaseCommand
from catalog.models import Product
import re


class Command(BaseCommand):
    help = 'Удаляет все строки "Размер:" из характеристик товаров (данные уже должны быть в "Характеристика:")'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без сохранения изменений',
        )
        parser.add_argument(
            '--catalog-type',
            type=str,
            choices=['retail', 'wholesale', 'all'],
            default='all',
            help='Тип каталога для обработки (retail, wholesale, all)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']

        # Фильтруем товары по типу каталога
        if catalog_type == 'all':
            products = Product.objects.filter(characteristics__isnull=False).exclude(characteristics='')
        else:
            products = Product.objects.filter(
                catalog_type=catalog_type,
                characteristics__isnull=False
            ).exclude(characteristics='')

        total = products.count()
        self.stdout.write(f'Найдено {total} товаров с характеристиками для обработки')

        removed_count = 0
        products_with_size = 0

        for product in products:
            if not product.characteristics:
                continue

            original_chars = product.characteristics
            char_lines = [line.strip() for line in original_chars.split('\n') if line.strip()]

            # Ищем строки, которые начинаются с "Размер:" или "Size:"
            has_size = False
            filtered_lines = []
            for line in char_lines:
                if ':' in line:
                    key = line.split(':', 1)[0].strip()
                    # Проверяем, не является ли это строкой "Размер:" или "Size:"
                    if 'размер' in key.lower() or 'size' in key.lower():
                        has_size = True
                        # Пропускаем эту строку (не добавляем в filtered_lines)
                        continue
                # Все остальные строки оставляем
                filtered_lines.append(line)

            # Если нашли и удалили строки "Размер:", обновляем товар
            if has_size:
                products_with_size += 1
                new_characteristics = '\n'.join(filtered_lines) if filtered_lines else ''

                if not dry_run:
                    product.characteristics = new_characteristics
                    product.save()
                    removed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Удален "Размер" из товара: {product.external_id or product.article} - {product.name[:50]}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'[DRY RUN] Будет удален "Размер" из: {product.external_id or product.article} - {product.name[:50]}'
                        )
                    )
                    self.stdout.write(f'  Было: "{original_chars[:100]}..."')
                    self.stdout.write(f'  Станет: "{new_characteristics[:100] if new_characteristics else "(пусто)"}..."')

        # Статистика
        self.stdout.write('\n' + '='*60)
        self.stdout.write('Статистика:')
        self.stdout.write(f'  Товаров с "Размер" в характеристиках: {products_with_size}')
        self.stdout.write(f'  Удалено строк "Размер": {removed_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nЭто был DRY RUN - изменения НЕ сохранены!'))
            self.stdout.write('Запустите без --dry-run для применения изменений.')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Все строки "Размер:" удалены из характеристик!'))
