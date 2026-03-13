"""
Команда для диагностики пропавших товаров.
Сравнивает количество товаров с остатками в 1С и на сайте.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product, Category
from django.db.models import Q


class Command(BaseCommand):
    help = 'Диагностика пропавших товаров'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ДИАГНОСТИКА ПРОПАВШИХ ТОВАРОВ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        # Ожидаемое количество товаров с остатками из 1С
        expected_count = 2504
        
        # Товары с остатками > 0
        products_with_stock = Product.objects.filter(quantity__gt=0)
        total_with_stock = products_with_stock.count()
        
        # Активные товары с остатками > 0
        active_with_stock = Product.objects.filter(
            quantity__gt=0,
            is_active=True
        )
        active_count = active_with_stock.count()
        
        # Товары с остатками > 0, но неактивные
        inactive_with_stock = Product.objects.filter(
            quantity__gt=0,
            is_active=False
        )
        inactive_count = inactive_with_stock.count()
        
        # Товары с остатками > 0 в розничном каталоге
        retail_with_stock = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0
        )
        retail_total = retail_with_stock.count()
        retail_active = retail_with_stock.filter(is_active=True).count()
        
        # Товары с остатками > 0 в оптовом каталоге
        wholesale_with_stock = Product.objects.filter(
            catalog_type='wholesale',
            quantity__gt=0
        )
        wholesale_total = wholesale_with_stock.count()
        wholesale_active = wholesale_with_stock.filter(is_active=True).count()
        
        self.stdout.write(f"Ожидается товаров с остатками из 1С: {expected_count}")
        self.stdout.write()
        self.stdout.write(f"В базе данных:")
        self.stdout.write(f"  - Всего товаров с остатками > 0: {total_with_stock}")
        self.stdout.write(f"  - Активных с остатками > 0: {active_count}")
        self.stdout.write(f"  - Неактивных с остатками > 0: {inactive_count}")
        self.stdout.write()
        self.stdout.write(f"Розничный каталог:")
        self.stdout.write(f"  - Всего с остатками > 0: {retail_total}")
        self.stdout.write(f"  - Активных с остатками > 0: {retail_active}")
        self.stdout.write()
        self.stdout.write(f"Оптовый каталог:")
        self.stdout.write(f"  - Всего с остатками > 0: {wholesale_total}")
        self.stdout.write(f"  - Активных с остатками > 0: {wholesale_active}")
        self.stdout.write()
        
        # Разница
        difference = expected_count - retail_active
        self.stdout.write(f"РАЗНИЦА: {expected_count} (ожидается) - {retail_active} (активных в розничном) = {difference}")
        self.stdout.write()
        
        # Товары с остатками > 0, но неактивные (должны быть активны)
        if inactive_count > 0:
            self.stdout.write(self.style.WARNING(f"⚠ Найдено {inactive_count} неактивных товаров с остатками > 0:"))
            self.stdout.write()
            
            # Без категории
            no_category = inactive_with_stock.filter(category__isnull=True).count()
            if no_category > 0:
                self.stdout.write(f"  - Без категории: {no_category}")
                examples = inactive_with_stock.filter(category__isnull=True)[:5]
                for p in examples:
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity})")
                self.stdout.write()
            
            # В неактивных категориях
            in_inactive_category = inactive_with_stock.filter(category__is_active=False).count()
            if in_inactive_category > 0:
                self.stdout.write(f"  - В неактивных категориях: {in_inactive_category}")
                examples = inactive_with_stock.filter(category__is_active=False)[:5]
                for p in examples:
                    cat_name = p.category.name if p.category else 'НЕТ'
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, категория: {cat_name}, количество: {p.quantity})")
                self.stdout.write()
            
            # С ценой = 0
            with_zero_price = inactive_with_stock.filter(
                Q(price=0) & Q(wholesale_price=0)
            ).count()
            if with_zero_price > 0:
                self.stdout.write(f"  - С ценой = 0: {with_zero_price}")
                examples = inactive_with_stock.filter(
                    Q(price=0) & Q(wholesale_price=0)
                )[:5]
                for p in examples:
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, цена: {p.price}, оптовая: {p.wholesale_price})")
                self.stdout.write()
            
            # Остальные (с ценой > 0, в активных категориях)
            others = inactive_with_stock.exclude(
                category__isnull=True
            ).exclude(
                category__is_active=False
            ).filter(
                Q(price__gt=0) | Q(wholesale_price__gt=0)
            ).count()
            if others > 0:
                self.stdout.write(f"  - С ценой > 0, в активных категориях: {others}")
                examples = inactive_with_stock.exclude(
                    category__isnull=True
                ).exclude(
                    category__is_active=False
                ).filter(
                    Q(price__gt=0) | Q(wholesale_price__gt=0)
                )[:5]
                for p in examples:
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, цена: {p.price})")
                self.stdout.write()
        
        # Товары без external_id (не были импортированы из 1С)
        without_external_id = Product.objects.filter(
            quantity__gt=0,
            external_id__isnull=True
        ).count()
        if without_external_id > 0:
            self.stdout.write(f"Товаров с остатками > 0 без external_id (не из 1С): {without_external_id}")
            self.stdout.write()
        
        # Товары с external_id, но неактивные
        with_external_id_inactive = Product.objects.filter(
            quantity__gt=0,
            is_active=False,
            external_id__isnull=False,
            external_id__gt=''
        ).count()
        if with_external_id_inactive > 0:
            self.stdout.write(f"Товаров из 1С с остатками > 0, но неактивных: {with_external_id_inactive}")
            self.stdout.write()
        
        # Рекомендации
        self.stdout.write("=" * 80)
        self.stdout.write("РЕКОМЕНДАЦИИ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if inactive_count > 0:
            self.stdout.write("Для активации неактивных товаров с остатками > 0:")
            self.stdout.write("  python manage.py restore_products_by_price")
            self.stdout.write()
        
        if no_category > 0 or in_inactive_category > 0:
            self.stdout.write("Для исправления товаров без категории или в неактивных категориях:")
            self.stdout.write("  python manage.py fix_missing_categories")
            self.stdout.write()
        
        self.stdout.write("=" * 80)
