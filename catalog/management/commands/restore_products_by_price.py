"""
Команда для восстановления товаров, которые были скрыты по старой логике,
но должны быть активны по новой логике (если price > 0 ИЛИ quantity > 0).
"""
from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Восстанавливает товары с price > 0 ИЛИ quantity > 0'

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

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']
        
        self.stdout.write("=" * 80)
        self.stdout.write("ВОССТАНОВЛЕНИЕ ТОВАРОВ ПО НОВОЙ ЛОГИКЕ")
        self.stdout.write("(активируем если price > 0 ИЛИ quantity > 0)")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ (dry-run) - изменения не будут применены"))
            self.stdout.write()
        
        # Товары, которые скрыты, но должны быть активны по новой логике
        filters = {
            'is_active': False,
        }
        
        if catalog_type != 'all':
            filters['catalog_type'] = catalog_type
        
        # Находим товары, которые должны быть активны
        all_inactive = Product.objects.filter(**filters)
        
        # Фильтруем по новой логике: price > 0 ИЛИ quantity > 0
        products_to_restore = []
        for product in all_inactive:
            if catalog_type == 'wholesale' or (catalog_type == 'all' and product.catalog_type == 'wholesale'):
                price = product.wholesale_price or 0
            else:
                price = product.price or 0
            
            quantity = product.quantity or 0
            
            if price > 0 or quantity > 0:
                products_to_restore.append(product)
        
        count = len(products_to_restore)
        
        self.stdout.write(f"Найдено скрытых товаров, которые должны быть активны: {count}")
        self.stdout.write()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Нет товаров для восстановления"))
            return
        
        # Статистика по типам каталога
        if catalog_type == 'all':
            retail_count = sum(1 for p in products_to_restore if p.catalog_type == 'retail')
            wholesale_count = sum(1 for p in products_to_restore if p.catalog_type == 'wholesale')
            self.stdout.write(f"  - Розничный каталог: {retail_count}")
            self.stdout.write(f"  - Оптовый каталог: {wholesale_count}")
            self.stdout.write()
        
        # Статистика по причинам
        with_price = sum(1 for p in products_to_restore if (p.price or 0) > 0 or (p.wholesale_price or 0) > 0)
        with_quantity = sum(1 for p in products_to_restore if (p.quantity or 0) > 0)
        with_both = sum(1 for p in products_to_restore if ((p.price or 0) > 0 or (p.wholesale_price or 0) > 0) and (p.quantity or 0) > 0)
        
        self.stdout.write(f"Статистика:")
        self.stdout.write(f"  - С ценой > 0: {with_price}")
        self.stdout.write(f"  - С количеством > 0: {with_quantity}")
        self.stdout.write(f"  - С ценой И количеством > 0: {with_both}")
        self.stdout.write()
        
        # Показываем примеры
        self.stdout.write("Примеры товаров для восстановления (первые 10):")
        for i, product in enumerate(products_to_restore[:10], 1):
            if product.catalog_type == 'wholesale':
                price = product.wholesale_price or 0
            else:
                price = product.price or 0
            quantity = product.quantity or 0
            self.stdout.write(
                f"  {i}. {product.name[:50]} (артикул: {product.article}, "
                f"цена: {price}, количество: {quantity}, каталог: {product.catalog_type})"
            )
        self.stdout.write()
        
        if not dry_run:
            # Восстанавливаем товары
            restored = 0
            for product in products_to_restore:
                if product.catalog_type == 'wholesale':
                    price = product.wholesale_price or 0
                else:
                    price = product.price or 0
                quantity = product.quantity or 0
                
                # Определяем availability
                if quantity > 0:
                    product.availability = 'in_stock'
                elif price > 0:
                    product.availability = 'order'
                else:
                    product.availability = 'out_of_stock'
                
                product.is_active = True
                product.save(update_fields=['is_active', 'availability'])
                restored += 1
            
            self.stdout.write(self.style.SUCCESS(f"✓ Восстановлено товаров: {restored}"))
            
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
