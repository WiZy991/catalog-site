"""
Команда для проверки количества товаров в базе данных.
"""

from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Проверяет количество товаров в базе данных'

    def handle(self, *args, **options):
        total = Product.objects.count()
        active = Product.objects.filter(is_active=True).count()
        with_quantity = Product.objects.filter(quantity__gt=0).count()
        retail = Product.objects.filter(catalog_type='retail').count()
        wholesale = Product.objects.filter(catalog_type='wholesale').count()
        retail_active = Product.objects.filter(catalog_type='retail', is_active=True).count()
        wholesale_active = Product.objects.filter(catalog_type='wholesale', is_active=True).count()
        
        self.stdout.write('=' * 60)
        self.stdout.write('СТАТИСТИКА ТОВАРОВ')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Всего товаров: {total}')
        self.stdout.write(f'  - Розничный каталог: {retail} (активных: {retail_active})')
        self.stdout.write(f'  - Оптовый каталог: {wholesale} (активных: {wholesale_active})')
        self.stdout.write('')
        self.stdout.write(f'Активных товаров: {active}')
        self.stdout.write(f'Товаров с количеством > 0: {with_quantity}')
        self.stdout.write(f'Товаров с количеством = 0: {Product.objects.filter(quantity=0).count()}')
        self.stdout.write('')
        self.stdout.write(f'Товаров в наличии (in_stock): {Product.objects.filter(availability="in_stock").count()}')
        self.stdout.write(f'Товаров нет в наличии (out_of_stock): {Product.objects.filter(availability="out_of_stock").count()}')
        self.stdout.write('=' * 60)
        
        # Проверяем товары в неактивных категориях
        products_in_inactive = Product.objects.filter(category__is_active=False).count()
        if products_in_inactive > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Найдено товаров в неактивных категориях: {products_in_inactive}'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Все товары находятся в активных категориях'))
        
        # Детальная статистика по розничному каталогу
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write('ДЕТАЛЬНАЯ СТАТИСТИКА ПО РОЗНИЧНОМУ КАТАЛОГУ')
        self.stdout.write('=' * 60)
        retail_with_stock = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=True,
            availability='in_stock'
        ).count()
        retail_active_with_stock = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=True
        ).count()
        retail_inactive_with_stock = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=False
        ).count()
        self.stdout.write(f'Товаров в розничном каталоге с остатком > 0: {Product.objects.filter(catalog_type="retail", quantity__gt=0).count()}')
        self.stdout.write(f'  - Активных с остатком > 0: {retail_active_with_stock}')
        self.stdout.write(f'  - Неактивных с остатком > 0: {retail_inactive_with_stock}')
        self.stdout.write(f'  - Активных с остатком > 0 и in_stock: {retail_with_stock}')
        self.stdout.write('')
        self.stdout.write(f'Ожидается товаров: 2504')
        if retail_with_stock < 2504:
            missing = 2504 - retail_with_stock
            self.stdout.write(self.style.WARNING(f'⚠ Не хватает товаров: {missing}'))
        elif retail_with_stock > 2504:
            extra = retail_with_stock - 2504
            self.stdout.write(self.style.WARNING(f'⚠ Больше чем ожидается: +{extra}'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Количество товаров соответствует ожидаемому'))
