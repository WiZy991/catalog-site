"""
Команда для пересборки данных товаров из имеющихся характеристик.

ВАЖНО: Для полного обновления (Размер, Кузов, Двигатель из 1С)
необходимо заново выполнить обмен из 1С. Эта команда обновляет
только то, что можно пересчитать из уже сохранённых данных.

Использование:
    python manage.py rebuild_product_data              # Все товары
    python manage.py rebuild_product_data --wholesale   # Только оптовые
    python manage.py rebuild_product_data --retail      # Только розничные
    python manage.py rebuild_product_data --dry-run     # Предпросмотр без сохранения
"""

from django.core.management.base import BaseCommand
from catalog.models import Product, ProductCharacteristic
import re
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Пересобирает характеристики и описание (применимость) товаров из имеющихся данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Предпросмотр изменений без сохранения'
        )
        parser.add_argument(
            '--wholesale',
            action='store_true',
            help='Только оптовые товары'
        )
        parser.add_argument(
            '--retail',
            action='store_true',
            help='Только розничные товары'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Определяем QuerySet
        products = Product.objects.all()
        if options['wholesale']:
            products = products.filter(catalog_type='wholesale')
        elif options['retail']:
            products = products.filter(catalog_type='retail')

        total = products.count()
        self.stdout.write(f'Всего товаров для обработки: {total}')
        if dry_run:
            self.stdout.write(self.style.WARNING('Режим DRY-RUN: изменения НЕ будут сохранены'))

        updated_chars = 0
        updated_desc = 0
        errors = 0

        # Проверяем, есть ли таблица ProductCharacteristic
        has_pc_table = False
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                if 'sqlite' in connection.vendor:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_productcharacteristic'")
                else:
                    cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'catalog_productcharacteristic')")
                has_pc_table = cursor.fetchone()[0] is not None
        except Exception:
            has_pc_table = False

        for idx, product in enumerate(products.iterator(chunk_size=500)):
            try:
                changed = False
                log_lines = []

                # === 1. Пересобираем характеристики из ProductCharacteristic ===
                if has_pc_table:
                    try:
                        pc_items = ProductCharacteristic.objects.filter(product=product).order_by('order')
                        if pc_items.exists():
                            new_chars_parts = []
                            new_desc_parts = []

                            for pc in pc_items:
                                name = pc.name.strip()
                                value = pc.value.strip()
                                name_lower = name.lower()

                                if not name or not value:
                                    continue

                                # Кузов → описание (Применимость)
                                if name_lower in ['кузов', 'body', 'тип кузова']:
                                    new_desc_parts.append(f'Кузов: {value}')
                                # Двигатель → описание (Применимость)
                                elif name_lower in ['двигатель', 'engine', 'мотор']:
                                    new_desc_parts.append(f'Двигатель: {value}')
                                # Размер → характеристики (всегда, без фильтрации)
                                elif 'размер' in name_lower or 'size' in name_lower:
                                    new_chars_parts.append(f'{name}: {value}')
                                # Остальные служебные — пропускаем
                                elif name_lower in ['артикул1', 'артикул 1', 'артикул2', 'артикул 2',
                                                     'марка', 'brand', 'бренд', 'oem', 'oem номер']:
                                    continue
                                else:
                                    # Обычная характеристика
                                    new_chars_parts.append(f'{name}: {value}')

                            # Обновляем описание (Применимость) если есть данные кузов/двигатель
                            if new_desc_parts:
                                new_desc = '\n'.join(new_desc_parts)
                                if product.description != new_desc:
                                    log_lines.append(f'  Описание: "{product.description}" → "{new_desc}"')
                                    product.description = new_desc
                                    changed = True
                                    updated_desc += 1

                            # Обновляем характеристики если есть
                            if new_chars_parts:
                                new_chars = '\n'.join(new_chars_parts)
                                if product.characteristics != new_chars:
                                    old_chars_preview = (product.characteristics or '')[:60]
                                    new_chars_preview = new_chars[:60]
                                    log_lines.append(f'  Характеристики: "{old_chars_preview}..." → "{new_chars_preview}..."')
                                    product.characteristics = new_chars
                                    changed = True
                                    updated_chars += 1
                    except Exception as e:
                        if 'no such table' not in str(e).lower():
                            logger.warning(f'Ошибка чтения ProductCharacteristic для {product.pk}: {e}')

                # === 2. Извлекаем Кузов/Двигатель из существующих характеристик ===
                if not changed and product.characteristics:
                    desc_parts = []
                    remaining_chars = []
                    for line in product.characteristics.strip().split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        if ':' in line:
                            key, val = line.split(':', 1)
                            key_lower = key.strip().lower()
                            if key_lower in ['кузов', 'body', 'тип кузова']:
                                desc_parts.append(line)
                            elif key_lower in ['двигатель', 'engine', 'мотор']:
                                desc_parts.append(line)
                            else:
                                remaining_chars.append(line)
                        else:
                            remaining_chars.append(line)

                    if desc_parts:
                        new_desc = '\n'.join(desc_parts)
                        if product.description != new_desc:
                            log_lines.append(f'  Описание (из характеристик): → "{new_desc}"')
                            product.description = new_desc
                            changed = True
                            updated_desc += 1
                        if remaining_chars:
                            new_chars = '\n'.join(remaining_chars)
                            if product.characteristics != new_chars:
                                product.characteristics = new_chars
                                changed = True
                                updated_chars += 1

                # === 3. Синхронизация фото: оптовый → розничный ===
                # (Не нужно — get_main_image() уже подтягивает автоматически)

                if changed:
                    if log_lines and (idx < 20 or idx % 500 == 0):
                        self.stdout.write(f'[{idx+1}/{total}] {product.name[:50]}')
                        for line in log_lines:
                            self.stdout.write(line)

                    if not dry_run:
                        product.save(update_fields=['characteristics', 'description'])

            except Exception as e:
                errors += 1
                if errors <= 10:
                    self.stdout.write(self.style.ERROR(f'Ошибка для товара {product.pk}: {e}'))

            if (idx + 1) % 1000 == 0:
                self.stdout.write(f'  Обработано {idx+1}/{total}...')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'=== Готово ==='))
        self.stdout.write(f'  Всего обработано: {total}')
        self.stdout.write(f'  Обновлены характеристики: {updated_chars}')
        self.stdout.write(f'  Обновлено описание (Применимость): {updated_desc}')
        self.stdout.write(f'  Ошибок: {errors}')
        if dry_run:
            self.stdout.write(self.style.WARNING('  ⚠ DRY-RUN: ничего не сохранено! Уберите --dry-run для применения.'))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '  ⚠ Для полного обновления полей Размер, Кузов, Двигатель\n'
                '    необходимо заново сделать обмен из 1С!'
            ))
