from django.core.management.base import BaseCommand
from django.db.models import Q
from catalog.models import Product


class Command(BaseCommand):
    help = 'Активирует товары в оптовом каталоге, у которых количество больше 0'

    def handle(self, *args, **options):
        # В оптовом каталоге товары показываются с остатком ИЛИ с оптовой ценой
        # Активируем все товары с остатком (независимо от цены)
        products_with_stock = Product.objects.filter(
            catalog_type='wholesale',
            quantity__gt=0,
            is_active=False
        )
        
        count_with_stock = products_with_stock.count()
        self.stdout.write(f'Найдено {count_with_stock} неактивных товаров с остатком')
        
        if count_with_stock > 0:
            # Активируем товары с остатком
            updated_with_stock = products_with_stock.update(
                is_active=True,
                availability='in_stock'
            )
            self.stdout.write(self.style.SUCCESS(f'Активировано {updated_with_stock} товаров с остатком'))
        else:
            self.stdout.write(self.style.SUCCESS('Все товары с остатком уже активны'))
        
        # Активируем товары без остатка, но с оптовой ценой (под заказ)
        products_with_price = Product.objects.filter(
            catalog_type='wholesale',
            quantity=0,
            wholesale_price__gt=0,
            is_active=False
        )
        
        count_with_price = products_with_price.count()
        self.stdout.write(f'Найдено {count_with_price} неактивных товаров без остатка, но с оптовой ценой')
        
        if count_with_price > 0:
            # Активируем товары с оптовой ценой (под заказ)
            updated_with_price = products_with_price.update(
                is_active=True,
                availability='order'
            )
            self.stdout.write(self.style.SUCCESS(f'Активировано {updated_with_price} товаров без остатка, но с оптовой ценой (под заказ)'))
        else:
            self.stdout.write(self.style.SUCCESS('Все товары с оптовой ценой уже активны'))
        
        # Деактивируем товары без остатка И без оптовой цены
        # ВАЖНО: Товары с оптовой ценой должны оставаться активными, даже если остаток = 0
        # Они будут показываться как "под заказ"
        products_without_stock_and_price = Product.objects.filter(
            catalog_type='wholesale',
            quantity=0,
            wholesale_price=0,
            is_active=True
        )
        deactivated = products_without_stock_and_price.update(
            is_active=False,
            availability='out_of_stock'
        )
        if deactivated > 0:
            self.stdout.write(self.style.WARNING(f'Деактивировано {deactivated} товаров без остатка и без оптовой цены'))
        
        # Обновляем availability для товаров без остатка, но с оптовой ценой
        # Они должны быть активны и показываться как "под заказ"
        products_without_stock_but_with_price = Product.objects.filter(
            catalog_type='wholesale',
            quantity=0,
            wholesale_price__gt=0,
            is_active=True
        )
        updated_to_order = products_without_stock_but_with_price.update(
            availability='order'
        )
        if updated_to_order > 0:
            self.stdout.write(self.style.SUCCESS(f'Обновлено {updated_to_order} товаров без остатка, но с оптовой ценой (статус: под заказ)'))
        
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