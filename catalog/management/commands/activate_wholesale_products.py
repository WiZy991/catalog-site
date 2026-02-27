from django.core.management.base import BaseCommand
from django.db.models import Q
from catalog.models import Product


class Command(BaseCommand):
    help = 'Активирует товары в оптовом каталоге, у которых количество больше 0'

    def handle(self, *args, **options):
        # В оптовом каталоге товары показываются только с остатком
        # Активируем все товары с остатком (независимо от цены)
        products = Product.objects.filter(
            catalog_type='wholesale',
            quantity__gt=0,
            is_active=False
        )
        
        count = products.count()
        self.stdout.write(f'Найдено {count} неактивных товаров с остатком')
        
        if count > 0:
            # Активируем товары с остатком
            updated = products.update(
                is_active=True,
                availability='in_stock'
            )
            self.stdout.write(self.style.SUCCESS(f'Активировано {updated} товаров'))
        else:
            self.stdout.write(self.style.SUCCESS('Все товары с остатком уже активны'))
        
        # Деактивируем товары без остатка
        products_without_stock = Product.objects.filter(
            catalog_type='wholesale',
            quantity=0,
            is_active=True
        )
        deactivated = products_without_stock.update(
            is_active=False,
            availability='out_of_stock'
        )
        if deactivated > 0:
            self.stdout.write(self.style.WARNING(f'Деактивировано {deactivated} товаров без остатка'))
        
        # Статистика
        total = Product.objects.filter(catalog_type='wholesale').count()
        active = Product.objects.filter(catalog_type='wholesale', is_active=True).count()
        with_stock = Product.objects.filter(catalog_type='wholesale', quantity__gt=0).count()
        active_with_stock = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True,
            quantity__gt=0
        ).count()
        with_price = Product.objects.filter(catalog_type='wholesale', wholesale_price__gt=0).count()
        active_with_stock_and_price = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True,
            quantity__gt=0,
            wholesale_price__gt=0
        ).count()
        
        self.stdout.write(f'\nСтатистика оптового каталога:')
        self.stdout.write(f'  Всего товаров: {total}')
        self.stdout.write(f'  С остатком: {with_stock}')
        self.stdout.write(f'  С оптовой ценой > 0: {with_price}')
        self.stdout.write(f'  Активных: {active}')
        self.stdout.write(f'  Активных с остатком: {active_with_stock}')
        self.stdout.write(f'  Активных с остатком и ценой: {active_with_stock_and_price}')