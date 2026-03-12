"""
Команда для исправления товаров без категории или в неактивных категориях.
Проблема: после добавления подкатегорий из keywords товары могут не находить свою категорию.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product, Category
from catalog.services import get_category_for_product


class Command(BaseCommand):
    help = 'Исправляет товары без категории или в неактивных категориях'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет исправлено, без фактического исправления',
        )
        parser.add_argument(
            '--catalog-type',
            type=str,
            choices=['retail', 'wholesale', 'all'],
            default='all',
            help='Тип каталога для исправления (retail, wholesale, all)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']
        
        self.stdout.write("=" * 80)
        self.stdout.write("ИСПРАВЛЕНИЕ ТОВАРОВ БЕЗ КАТЕГОРИИ ИЛИ В НЕАКТИВНЫХ КАТЕГОРИЯХ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ (dry-run) - изменения не будут применены"))
            self.stdout.write()
        
        # Товары без категории
        filters_no_category = {
            'category__isnull': True,
        }
        
        # Товары в неактивных категориях
        filters_inactive_category = {
            'category__is_active': False,
        }
        
        if catalog_type != 'all':
            filters_no_category['catalog_type'] = catalog_type
            filters_inactive_category['catalog_type'] = catalog_type
        
        products_no_category = Product.objects.filter(**filters_no_category)
        products_inactive_category = Product.objects.filter(**filters_inactive_category)
        
        count_no_category = products_no_category.count()
        count_inactive_category = products_inactive_category.count()
        
        self.stdout.write(f"Найдено товаров без категории: {count_no_category}")
        self.stdout.write(f"Найдено товаров в неактивных категориях: {count_inactive_category}")
        self.stdout.write()
        
        if count_no_category == 0 and count_inactive_category == 0:
            self.stdout.write(self.style.SUCCESS("Нет товаров для исправления"))
            return
        
        # Исправляем товары без категории
        fixed_no_category = 0
        if count_no_category > 0:
            self.stdout.write(f"Исправление товаров без категории ({count_no_category}):")
            for product in products_no_category[:100]:  # Ограничиваем для производительности
                category = get_category_for_product(product.name)
                if category:
                    if not dry_run:
                        product.category = category
                        product.save(update_fields=['category'])
                    fixed_no_category += 1
                    if fixed_no_category <= 10:
                        self.stdout.write(
                            f"  ✓ {product.name[:50]} -> {category.name}"
                        )
                else:
                    # Если категория не найдена, используем первую активную корневую
                    fallback = Category.objects.filter(parent=None, is_active=True).first()
                    if fallback:
                        if not dry_run:
                            product.category = fallback
                            product.save(update_fields=['category'])
                        fixed_no_category += 1
                        if fixed_no_category <= 10:
                            self.stdout.write(
                                f"  ⚠ {product.name[:50]} -> {fallback.name} (fallback)"
                            )
            
            if count_no_category > 100:
                self.stdout.write(f"  ... и еще {count_no_category - 100} товаров")
            self.stdout.write()
        
        # Исправляем товары в неактивных категориях
        fixed_inactive = 0
        if count_inactive_category > 0:
            self.stdout.write(f"Исправление товаров в неактивных категориях ({count_inactive_category}):")
            for product in products_inactive_category[:100]:  # Ограничиваем для производительности
                # Пробуем найти активную категорию по названию товара
                category = get_category_for_product(product.name)
                if category and category.is_active:
                    if not dry_run:
                        product.category = category
                        product.save(update_fields=['category'])
                    fixed_inactive += 1
                    if fixed_inactive <= 10:
                        self.stdout.write(
                            f"  ✓ {product.name[:50]} ({product.category.name if product.category else 'нет'}) -> {category.name}"
                        )
                else:
                    # Ищем активную родительскую категорию
                    current_cat = product.category
                    active_parent = None
                    while current_cat:
                        if current_cat.parent and current_cat.parent.is_active:
                            active_parent = current_cat.parent
                            break
                        current_cat = current_cat.parent
                    
                    if active_parent:
                        if not dry_run:
                            product.category = active_parent
                            product.save(update_fields=['category'])
                        fixed_inactive += 1
                        if fixed_inactive <= 10:
                            self.stdout.write(
                                f"  ✓ {product.name[:50]} -> {active_parent.name} (родительская)"
                            )
                    else:
                        # Используем первую активную корневую категорию
                        fallback = Category.objects.filter(parent=None, is_active=True).first()
                        if fallback:
                            if not dry_run:
                                product.category = fallback
                                product.save(update_fields=['category'])
                            fixed_inactive += 1
                            if fixed_inactive <= 10:
                                self.stdout.write(
                                    f"  ⚠ {product.name[:50]} -> {fallback.name} (fallback)"
                                )
            
            if count_inactive_category > 100:
                self.stdout.write(f"  ... и еще {count_inactive_category - 100} товаров")
            self.stdout.write()
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"✓ Исправлено товаров без категории: {fixed_no_category}"))
            self.stdout.write(self.style.SUCCESS(f"✓ Исправлено товаров в неактивных категориях: {fixed_inactive}"))
        else:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ - товары НЕ были исправлены"))
            self.stdout.write("Запустите команду без --dry-run для фактического исправления")
        
        self.stdout.write()
        self.stdout.write("=" * 80)
