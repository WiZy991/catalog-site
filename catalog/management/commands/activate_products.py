"""
Команда для активации товаров, которые должны быть активны, но не активированы.
Активирует товары в зависимости от типа каталога:
- Розничный каталог: товары с остатком > 0 ИЛИ ценой > 0
- Оптовый каталог: товары с остатком > 0
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from catalog.models import Product


class Command(BaseCommand):
    help = 'Активирует товары, которые должны быть активны по остатку или цене'

    def handle(self, *args, **options):
        # Статистика ДО активации
        retail_should_be_active = Product.objects.filter(
            catalog_type='retail',
            is_active=False
        ).filter(
            Q(quantity__gt=0) | Q(price__gt=0)
        )
        
        retail_should_be_active_count = retail_should_be_active.count()
        
        wholesale_should_be_active = Product.objects.filter(
            catalog_type='wholesale',
            is_active=False,
            quantity__gt=0
        )
        
        wholesale_should_be_active_count = wholesale_should_be_active.count()
        
        self.stdout.write(f'Найдено товаров для активации:')
        self.stdout.write(f'  Розничный каталог: {retail_should_be_active_count}')
        if retail_should_be_active_count > 0:
            # Показываем примеры товаров, которые должны быть активированы
            examples = retail_should_be_active[:5]
            for p in examples:
                self.stdout.write(f'    - {p.article} ({p.name[:50]}): остаток={p.quantity}, цена={p.price}')
        
        self.stdout.write(f'  Оптовый каталог: {wholesale_should_be_active_count}')
        if wholesale_should_be_active_count > 0:
            # Показываем примеры товаров, которые должны быть активированы
            examples = wholesale_should_be_active[:5]
            for p in examples:
                self.stdout.write(f'    - {p.article} ({p.name[:50]}): остаток={p.quantity}, оптовая цена={p.wholesale_price}')
        
        # Активируем товары в розничном каталоге
        retail_products = Product.objects.filter(
            catalog_type='retail',
            is_active=False
        ).filter(
            Q(quantity__gt=0) | Q(price__gt=0)
        )
        
        retail_count = retail_products.update(is_active=True)
        self.stdout.write(
            self.style.SUCCESS(f'Активировано товаров в розничном каталоге: {retail_count}')
        )
        
        # Активируем товары в оптовом каталоге
        wholesale_products = Product.objects.filter(
            catalog_type='wholesale',
            is_active=False,
            quantity__gt=0
        )
        
        wholesale_count = wholesale_products.update(is_active=True)
        self.stdout.write(
            self.style.SUCCESS(f'Активировано товаров в оптовом каталоге: {wholesale_count}')
        )
        
        # Дополнительная статистика
        retail_total = Product.objects.filter(catalog_type='retail').count()
        retail_active = Product.objects.filter(catalog_type='retail', is_active=True).count()
        retail_with_stock = Product.objects.filter(catalog_type='retail', quantity__gt=0).count()
        retail_with_price = Product.objects.filter(catalog_type='retail', price__gt=0).count()
        
        wholesale_total = Product.objects.filter(catalog_type='wholesale').count()
        wholesale_active = Product.objects.filter(catalog_type='wholesale', is_active=True).count()
        wholesale_with_stock = Product.objects.filter(catalog_type='wholesale', quantity__gt=0).count()
        
        self.stdout.write(f'\nСтатистика розничного каталога:')
        self.stdout.write(f'  Всего товаров: {retail_total}')
        self.stdout.write(f'  С остатком: {retail_with_stock}')
        self.stdout.write(f'  С ценой > 0: {retail_with_price}')
        self.stdout.write(f'  Активных: {retail_active}')
        
        self.stdout.write(f'\nСтатистика оптового каталога:')
        self.stdout.write(f'  Всего товаров: {wholesale_total}')
        self.stdout.write(f'  С остатком: {wholesale_with_stock}')
        self.stdout.write(f'  Активных: {wholesale_active}')
        
        # Деактивируем товары, которые не должны быть активны
        # Розничный каталог: товары без остатка и без цены
        retail_deactivated = Product.objects.filter(
            catalog_type='retail',
            is_active=True
        ).filter(
            quantity=0,
            price=0
        ).update(is_active=False)
        
        if retail_deactivated > 0:
            self.stdout.write(
                self.style.WARNING(f'Деактивировано товаров в розничном каталоге (нет остатка и цены): {retail_deactivated}')
            )
        
        # Оптовый каталог: товары без остатка
        wholesale_deactivated = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True,
            quantity=0
        ).update(is_active=False)
        
        if wholesale_deactivated > 0:
            self.stdout.write(
                self.style.WARNING(f'Деактивировано товаров в оптовом каталоге (нет остатка): {wholesale_deactivated}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nВсего активировано: {retail_count + wholesale_count}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Всего деактивировано: {retail_deactivated + wholesale_deactivated}')
        )
