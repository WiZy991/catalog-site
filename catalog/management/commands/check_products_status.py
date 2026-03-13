"""
Команда для проверки статуса товаров после обмена.
Показывает сколько товаров создано, активировано и почему некоторые не активны.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product
from django.db.models import Q


class Command(BaseCommand):
    help = 'Проверяет статус товаров после обмена с 1С'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ПРОВЕРКА СТАТУСА ТОВАРОВ ПОСЛЕ ОБМЕНА")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        # Все товары из 1С
        all_from_1c = Product.objects.filter(
            external_id__isnull=False,
            external_id__gt=''
        )
        
        total_count = all_from_1c.count()
        retail_count = all_from_1c.filter(catalog_type='retail').count()
        wholesale_count = all_from_1c.filter(catalog_type='wholesale').count()
        
        self.stdout.write(f"Всего товаров из 1С: {total_count}")
        self.stdout.write(f"  - Розничный каталог: {retail_count}")
        self.stdout.write(f"  - Оптовый каталог: {wholesale_count}")
        self.stdout.write()
        
        # Активные товары
        active_from_1c = all_from_1c.filter(is_active=True)
        active_count = active_from_1c.count()
        active_retail = active_from_1c.filter(catalog_type='retail').count()
        active_wholesale = active_from_1c.filter(catalog_type='wholesale').count()
        
        self.stdout.write(f"Активных товаров из 1С: {active_count}")
        self.stdout.write(f"  - Розничный каталог: {active_retail}")
        self.stdout.write(f"  - Оптовый каталог: {active_wholesale}")
        self.stdout.write()
        
        # Неактивные товары
        inactive_from_1c = all_from_1c.filter(is_active=False)
        inactive_count = inactive_from_1c.count()
        
        if inactive_count > 0:
            self.stdout.write(f"Неактивных товаров из 1С: {inactive_count}")
            self.stdout.write()
            
            # Причины неактивности
            # С quantity = 0
            inactive_qty_zero = inactive_from_1c.filter(quantity=0).count()
            if inactive_qty_zero > 0:
                self.stdout.write(f"  - С количеством = 0: {inactive_qty_zero}")
            
            # С ценой = 0
            inactive_price_zero_retail = inactive_from_1c.filter(
                catalog_type='retail',
                price=0
            ).count()
            inactive_price_zero_wholesale = inactive_from_1c.filter(
                catalog_type='wholesale',
                wholesale_price=0
            ).count()
            if inactive_price_zero_retail > 0 or inactive_price_zero_wholesale > 0:
                self.stdout.write(f"  - С ценой = 0 (розничный): {inactive_price_zero_retail}")
                self.stdout.write(f"  - С оптовой ценой = 0: {inactive_price_zero_wholesale}")
            
            # С quantity = 0 И price = 0
            inactive_both_zero_retail = inactive_from_1c.filter(
                catalog_type='retail',
                quantity=0,
                price=0
            ).count()
            inactive_both_zero_wholesale = inactive_from_1c.filter(
                catalog_type='wholesale',
                quantity=0,
                wholesale_price=0
            ).count()
            if inactive_both_zero_retail > 0 or inactive_both_zero_wholesale > 0:
                self.stdout.write(f"  - С количеством = 0 И ценой = 0 (розничный): {inactive_both_zero_retail}")
                self.stdout.write(f"  - С количеством = 0 И оптовой ценой = 0: {inactive_both_zero_wholesale}")
            
            # С quantity > 0 И price > 0, но неактивные (должны быть активны!)
            should_be_active_retail = inactive_from_1c.filter(
                catalog_type='retail',
                quantity__gt=0,
                price__gt=0
            ).count()
            should_be_active_wholesale = inactive_from_1c.filter(
                catalog_type='wholesale',
                quantity__gt=0,
                wholesale_price__gt=0
            ).count()
            if should_be_active_retail > 0 or should_be_active_wholesale > 0:
                self.stdout.write()
                self.stdout.write(self.style.WARNING(f"⚠ ПРОБЛЕМА: Товаров с quantity > 0 И price > 0, но неактивных:"))
                self.stdout.write(self.style.WARNING(f"  - Розничный каталог: {should_be_active_retail}"))
                self.stdout.write(self.style.WARNING(f"  - Оптовый каталог: {should_be_active_wholesale}"))
                self.stdout.write()
                self.stdout.write("  Примеры товаров, которые должны быть активны:")
                examples_retail = inactive_from_1c.filter(
                    catalog_type='retail',
                    quantity__gt=0,
                    price__gt=0
                )[:5]
                for p in examples_retail:
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, цена: {p.price})")
                if should_be_active_wholesale > 0:
                    examples_wholesale = inactive_from_1c.filter(
                        catalog_type='wholesale',
                        quantity__gt=0,
                        wholesale_price__gt=0
                    )[:5]
                    for p in examples_wholesale:
                        self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, оптовая цена: {p.wholesale_price})")
        
        # Товары, которые должны показываться на сайте (quantity > 0 И price > 0)
        should_show_retail = Product.objects.filter(
            catalog_type='retail',
            external_id__isnull=False,
            external_id__gt='',
            quantity__gt=0,
            price__gt=0,
            is_active=True,
            category__isnull=False,
            category__is_active=True
        ).count()
        
        self.stdout.write()
        self.stdout.write("=" * 80)
        self.stdout.write("ИТОГО")
        self.stdout.write("=" * 80)
        self.stdout.write()
        self.stdout.write(f"Товаров из 1С всего: {total_count}")
        self.stdout.write(f"Товаров активных: {active_count}")
        self.stdout.write(f"Товаров неактивных: {inactive_count}")
        self.stdout.write()
        self.stdout.write(f"Товаров, которые ДОЛЖНЫ показываться на сайте (quantity > 0 И price > 0): {should_show_retail}")
        self.stdout.write()
        
        if should_be_active_retail > 0 or should_be_active_wholesale > 0:
            self.stdout.write(self.style.ERROR("РЕКОМЕНДАЦИЯ: Запустите команду для активации товаров:"))
            self.stdout.write("  python manage.py restore_products_by_price")
            self.stdout.write()
        
        self.stdout.write("=" * 80)
