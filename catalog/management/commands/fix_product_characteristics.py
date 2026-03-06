from django.core.management.base import BaseCommand
from django.db import transaction
from catalog.models import Product
from catalog.services import parse_product_name
import re


class Command(BaseCommand):
    help = 'Исправляет характеристики и применимость существующих товаров: извлекает полный "Размер" из названия и удаляет Артикул2 из применимости'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет исправлено, без сохранения изменений',
        )
        parser.add_argument(
            '--catalog-type',
            type=str,
            choices=['retail', 'wholesale', 'all'],
            default='all',
            help='Тип каталога для обработки (retail, wholesale, all)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Ограничить количество обрабатываемых товаров (для тестирования)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']
        limit = options.get('limit')

        # Фильтруем товары по типу каталога
        if catalog_type == 'all':
            products = Product.objects.all()
        else:
            products = Product.objects.filter(catalog_type=catalog_type)

        if limit:
            products = products[:limit]

        total = products.count()
        self.stdout.write(f'Найдено {total} товаров для обработки')

        fixed_characteristics = 0
        fixed_applicability = 0
        fixed_both = 0

        for product in products:
            changed = False
            char_changed = False
            appl_changed = False
            original_characteristics = product.characteristics or ''
            original_applicability = product.applicability or ''
            original_cross_numbers = product.cross_numbers or ''

            # 1. Исправляем характеристики - извлекаем полный "Размер" из названия
            if product.name:
                parsed = parse_product_name(product.name)
                
                # Ищем полное значение "Размер" в названии
                # Формат может быть: "12V/140А/ПЛ.РЕМ.6Д/ОВ.Ф/ЗКОНТ" или "12V/80А/ПЛ. РЕМ.5Д/ОВ.Ф./ЗКОНТ"
                size_value = None
                
                # Сначала ищем в скобках в конце названия (самый частый случай)
                # Пример: "Генератор (NISSAN, 23100-EN00B, /EW80A, MR20DE/MR18DE, 12V/140А/ПЛ.РЕМ.6Д/ОВ.Ф/ЗКОНТ)"
                bracket_matches = re.findall(r'\(([^)]+)\)', product.name)
                
                # Ищем значение "Размер" в скобках - это значение с "/" и содержит "V" и "А"
                for bracket_content in bracket_matches:
                    # Разбиваем содержимое скобок по запятым
                    parts = [p.strip() for p in bracket_content.split(',')]
                    for part in parts:
                        part = part.strip()
                        # Ищем значение, которое содержит "/" и выглядит как размер (12V/140А/...)
                        # Паттерн: начинается с цифр+V, содержит /, затем цифры+А, и еще части через /
                        if '/' in part and re.search(r'\d+V.*/\d+[АA]', part, re.IGNORECASE):
                            # Проверяем, что это не артикул (не начинается с /) и не код модели
                            if not part.startswith('/') and not re.match(r'^[A-Z0-9]{1,6}$', part):
                                size_value = part.strip()
                                break
                    if size_value:
                        break
                
                # Если не нашли в скобках, пробуем найти в названии напрямую
                if not size_value:
                    size_pattern = r'(\d+V(?:-\d+V)?/\d+[АA](?:/[^,)\s]+)*)'
                    size_matches = re.findall(size_pattern, product.name, re.IGNORECASE)
                    if size_matches:
                        # Берем самое длинное совпадение (оно должно быть полным)
                        size_value = max(size_matches, key=len)
                
                # Если нашли полное значение "Размер", исправляем "Характеристика"
                if size_value:
                    # Проверяем текущие характеристики
                    current_chars = product.characteristics or ''
                    char_lines = [line.strip() for line in current_chars.split('\n') if line.strip()]
                    
                    # Ищем строку "Характеристика: ..." в характеристиках
                    characteristic_found = False
                    for i, line in enumerate(char_lines):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key_stripped = key.strip()
                            value_stripped = value.strip()
                            
                            # Ищем "Характеристика" (не "Размер"!)
                            if 'характеристика' in key_stripped.lower() or 'characteristic' in key_stripped.lower():
                                # Проверяем, не является ли значение только частью (например, "РЕМ")
                                if len(value_stripped) < len(size_value) and value_stripped.upper() in size_value.upper():
                                    # Это обрезанное значение - заменяем на полное значение из "Размер"
                                    char_lines[i] = f"{key_stripped}: {size_value}"
                                    changed = True
                                    char_changed = True
                                    characteristic_found = True
                                    break
                                # Если значение уже полное, не трогаем
                                elif size_value.upper() in value_stripped.upper() or value_stripped.upper() in size_value.upper():
                                    # Значение уже содержит размер или размер содержит значение - не трогаем
                                    characteristic_found = True
                                    break
                    
                    # Если "Характеристика" не найдена, но есть "Размер" - заменяем "Размер" на "Характеристика"
                    if not characteristic_found:
                        for i, line in enumerate(char_lines):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                if 'размер' in key.lower() or 'size' in key.lower():
                                    # Заменяем "Размер: ..." на "Характеристика: ..." с полным значением
                                    char_lines[i] = f"Характеристика: {size_value}"
                                    changed = True
                                    char_changed = True
                                    break
                        
                        # Если не нашли ни "Характеристика", ни "Размер", добавляем "Характеристика"
                        if not changed:
                            char_lines.append(f"Характеристика: {size_value}")
                            changed = True
                            char_changed = True
                    
                    if changed:
                        product.characteristics = '\n'.join(char_lines)

            # 2. Исправляем применимость - удаляем Артикул2 (значения, начинающиеся с "/")
            if product.applicability:
                applicability_parts = [p.strip() for p in product.applicability.split(',') if p.strip()]
                original_parts = applicability_parts.copy()
                
                # Находим значения, начинающиеся с "/" (Артикул2)
                article2_values = []
                filtered_parts = []
                for part in applicability_parts:
                    if part.startswith('/'):
                        # Это Артикул2 - перемещаем в кросс-номера
                        article2_value = part[1:] if part.startswith('/') else part  # Убираем "/"
                        article2_values.append(article2_value)
                    else:
                        filtered_parts.append(part)
                
                # Если нашли Артикул2 в применимости, исправляем
                if article2_values:
                    # Обновляем применимость (убираем Артикул2)
                    if filtered_parts:
                        product.applicability = ', '.join(filtered_parts)
                    else:
                        product.applicability = ''
                    
                    # Добавляем Артикул2 в кросс-номера
                    existing_cross = [c.strip() for c in (product.cross_numbers or '').split(',') if c.strip()]
                    for article2 in article2_values:
                        if article2 not in existing_cross:
                            existing_cross.append(article2)
                    
                    if existing_cross:
                        product.cross_numbers = ', '.join(existing_cross)
                    
                    changed = True
                    appl_changed = True

            # Сохраняем изменения и обновляем статистику
            if changed:
                if char_changed and appl_changed:
                    fixed_both += 1
                elif char_changed:
                    fixed_characteristics += 1
                elif appl_changed:
                    fixed_applicability += 1
                
                if not dry_run:
                    product.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Исправлен товар: {product.external_id or product.article} - {product.name[:50]}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'[DRY RUN] Будет исправлен: {product.external_id or product.article} - {product.name[:50]}'
                        )
                    )
                    if original_characteristics != (product.characteristics or ''):
                        self.stdout.write(f'  Характеристики: "{original_characteristics[:80]}..." → "{product.characteristics[:80] if product.characteristics else ""}..."')
                    if original_applicability != (product.applicability or ''):
                        self.stdout.write(f'  Применимость: "{original_applicability}" → "{product.applicability}"')
                    if original_cross_numbers != (product.cross_numbers or ''):
                        self.stdout.write(f'  Кросс-номера: "{original_cross_numbers}" → "{product.cross_numbers}"')

        # Статистика
        self.stdout.write('\n' + '='*60)
        self.stdout.write('Статистика исправлений:')
        self.stdout.write(f'  Исправлено характеристик: {fixed_characteristics}')
        self.stdout.write(f'  Исправлено применимости: {fixed_applicability}')
        self.stdout.write(f'  Исправлено и то, и другое: {fixed_both}')
        self.stdout.write(f'  Всего исправлено товаров: {fixed_characteristics + fixed_applicability + fixed_both}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nЭто был DRY RUN - изменения НЕ сохранены!'))
            self.stdout.write('Запустите без --dry-run для применения изменений.')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Все изменения сохранены!'))
