"""
Команда для проверки, действительно ли товары обновлены в базе после активации.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product
from django.db.models import Q


class Command(BaseCommand):
    help = 'Проверяет, действительно ли товары обновлены в базе'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ПРОВЕРКА ОБНОВЛЕНИЯ ТОВАРОВ В БАЗЕ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        # Проверяем товары с external_id, которые должны быть активны
        # (есть в offers.xml с quantity > 0 и price > 0)
        
        # Товары с остатками > 0
        products_with_stock = Product.objects.filter(
            external_id__isnull=False,
            external_id__gt='',
            quantity__gt=0
        )
        
        retail_with_stock = products_with_stock.filter(catalog_type='retail')
        wholesale_with_stock = products_with_stock.filter(catalog_type='wholesale')
        
        self.stdout.write(f"Товаров с остатками > 0:")
        self.stdout.write(f"  - Розничный каталог: {retail_with_stock.count()}")
        self.stdout.write(f"  - Оптовый каталог: {wholesale_with_stock.count()}")
        self.stdout.write()
        
        # Товары с остатками > 0 и ценой > 0
        retail_with_stock_and_price = retail_with_stock.filter(price__gt=0)
        wholesale_with_stock_and_price = wholesale_with_stock.filter(wholesale_price__gt=0)
        
        self.stdout.write(f"Товаров с остатками > 0 И ценой > 0:")
        self.stdout.write(f"  - Розничный каталог: {retail_with_stock_and_price.count()}")
        self.stdout.write(f"  - Оптовый каталог: {wholesale_with_stock_and_price.count()}")
        self.stdout.write()
        
        # Товары с остатками > 0 и ценой > 0, но неактивные
        retail_inactive = retail_with_stock_and_price.filter(is_active=False)
        wholesale_inactive = wholesale_with_stock_and_price.filter(is_active=False)
        
        self.stdout.write(f"Товаров с остатками > 0 И ценой > 0, но НЕАКТИВНЫХ:")
        self.stdout.write(f"  - Розничный каталог: {retail_inactive.count()}")
        self.stdout.write(f"  - Оптовый каталог: {wholesale_inactive.count()}")
        self.stdout.write()
        
        if retail_inactive.count() > 0 or wholesale_inactive.count() > 0:
            self.stdout.write(self.style.WARNING("⚠ ПРОБЛЕМА: Товары обновлены, но не активированы!"))
            self.stdout.write()
            self.stdout.write("Примеры неактивных товаров с остатками и ценой:")
            
            examples_retail = retail_inactive[:5]
            for p in examples_retail:
                self.stdout.write(f"  - {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, цена: {p.price}, is_active: {p.is_active})")
            
            if wholesale_inactive.count() > 0:
                examples_wholesale = wholesale_inactive[:5]
                for p in examples_wholesale:
                    self.stdout.write(f"  - {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, оптовая цена: {p.wholesale_price}, is_active: {p.is_active})")
            
            self.stdout.write()
            self.stdout.write("РЕКОМЕНДАЦИЯ: Запустите команду для активации:")
            self.stdout.write("  python manage.py restore_products_by_price")
        
        # Товары активные с остатками > 0 и ценой > 0
        retail_active = retail_with_stock_and_price.filter(is_active=True)
        wholesale_active = wholesale_with_stock_and_price.filter(is_active=True)
        
        self.stdout.write("=" * 80)
        self.stdout.write("ИТОГО")
        self.stdout.write("=" * 80)
        self.stdout.write()
        self.stdout.write(f"Товаров с остатками > 0 И ценой > 0 И активных:")
        self.stdout.write(f"  - Розничный каталог: {retail_active.count()}")
        self.stdout.write(f"  - Оптовый каталог: {wholesale_active.count()}")
        self.stdout.write()
        
        if retail_active.count() < 2000:
            self.stdout.write(self.style.ERROR(
                f"⚠ ПРОБЛЕМА: Должно быть около 2503 активных товаров, а сейчас только {retail_active.count()}"
            ))
        
        self.stdout.write("=" * 80)
