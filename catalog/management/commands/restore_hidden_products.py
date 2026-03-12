"""
Команда для восстановления товаров, которые были скрыты из-за проблем с категориями.
Восстанавливает товары с количеством > 0 и исправляет их категории.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product, Category
from catalog.services import get_category_for_product


class Command(BaseCommand):
    help = 'Восстанавливает скрытые товары с количеством > 0 и исправляет их категории'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет восстановлено, без фактического восстановления',
        )
        parser.add_argument(
            '--catalog-type',
            type=str,
            choices=['retail', 'wholesale', 'all'],
            default='all',
            help='Тип каталога для восстановления (retail, wholesale, all)',
        )
        parser.add_argument(
            '--fix-categories',
            action='store_true',
            help='Также исправлять категории товаров (без категории или в неактивных)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']
        fix_categories = options['fix_categories']
        
        self.stdout.write("=" * 80)
        self.stdout.write("ВОССТАНОВЛЕНИЕ СКРЫТЫХ ТОВАРОВ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ (dry-run) - изменения не будут применены"))
            self.stdout.write()
        
        # Товары, которые были скрыты, но имеют количество > 0
        filters = {
            'is_active': False,
            'quantity__gt': 0,
        }
        
        if catalog_type != 'all':
            filters['catalog_type'] = catalog_type
        
        products_to_restore = Product.objects.filter(**filters)
        count = products_to_restore.count()
        
        self.stdout.write(f"Найдено скрытых товаров с количеством > 0: {count}")
        self.stdout.write()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Нет товаров для восстановления"))
            if not fix_categories:
                return
        
        # Статистика по типам каталога
        if catalog_type == 'all':
            retail_count = products_to_restore.filter(catalog_type='retail').count()
            wholesale_count = products_to_restore.filter(catalog_type='wholesale').count()
            self.stdout.write(f"  - Розничный каталог: {retail_count}")
            self.stdout.write(f"  - Оптовый каталог: {wholesale_count}")
            self.stdout.write()
        
        # Проверяем товары без категории или в неактивных категориях
        products_no_category = products_to_restore.filter(category__isnull=True).count()
        products_inactive_category = products_to_restore.filter(category__is_active=False).count()
        
        if products_no_category > 0 or products_inactive_category > 0:
            self.stdout.write(f"Товары с проблемами категорий:")
            self.stdout.write(f"  - Без категории: {products_no_category}")
            self.stdout.write(f"  - В неактивных категориях: {products_inactive_category}")
            self.stdout.write()
        
        restored = 0
        fixed_categories = 0
        
        # Восстанавливаем товары
        for product in products_to_restore[:500]:  # Ограничиваем для производительности
            # Исправляем категорию, если нужно
            if fix_categories:
                if not product.category or not product.category.is_active:
                    category = get_category_for_product(product.name)
                    if category and category.is_active:
                        if not dry_run:
                            product.category = category
                        fixed_categories += 1
                    elif not product.category:
                        # Если категория не найдена, используем первую активную корневую
                        fallback = Category.objects.filter(parent=None, is_active=True).first()
                        if fallback:
                            if not dry_run:
                                product.category = fallback
                            fixed_categories += 1
            
            # Восстанавливаем товар
            if not dry_run:
                product.is_active = True
                product.availability = 'in_stock'
                product.save(update_fields=['is_active', 'availability', 'category'])
            restored += 1
            
            if restored <= 10:
                self.stdout.write(
                    f"  ✓ {product.name[:50]} (артикул: {product.article}, "
                    f"количество: {product.quantity}, каталог: {product.catalog_type})"
                )
        
        if count > 500:
            self.stdout.write(f"  ... и еще {count - 500} товаров")
        self.stdout.write()
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"✓ Восстановлено товаров: {restored}"))
            if fix_categories:
                self.stdout.write(self.style.SUCCESS(f"✓ Исправлено категорий: {fixed_categories}"))
            
            # Статистика после восстановления
            if catalog_type == 'all':
                retail_active = Product.objects.filter(
                    catalog_type='retail',
                    is_active=True
                ).count()
                wholesale_active = Product.objects.filter(
                    catalog_type='wholesale',
                    is_active=True
                ).count()
                self.stdout.write()
                self.stdout.write("Статистика после восстановления:")
                self.stdout.write(f"  - Активных в розничном каталоге: {retail_active}")
                self.stdout.write(f"  - Активных в оптовом каталоге: {wholesale_active}")
        else:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ - товары НЕ были восстановлены"))
            self.stdout.write("Запустите команду без --dry-run для фактического восстановления")
        
        self.stdout.write()
        self.stdout.write("=" * 80)
