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
            is_active=False
        ).filter(
            Q(quantity__gt=0) | Q(wholesale_price__gt=0)
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
        # ВАЖНО: Товар должен быть активен, если есть остаток ИЛИ есть цена
        retail_products = Product.objects.filter(
            catalog_type='retail',
            is_active=False
        ).filter(
            Q(quantity__gt=0) | Q(price__gt=0)
        )
        
        # Также обновляем availability для товаров с ценой, но без остатка
        retail_products_to_activate = list(retail_products.values_list('id', flat=True))
        retail_count = retail_products.update(
            is_active=True,
            availability='in_stock'  # Будет обновлено ниже
        )
        
        # Обновляем availability правильно
        Product.objects.filter(
            id__in=retail_products_to_activate,
            quantity__gt=0
        ).update(availability='in_stock')
        
        Product.objects.filter(
            id__in=retail_products_to_activate,
            quantity=0,
            price__gt=0
        ).update(availability='order')
        self.stdout.write(
            self.style.SUCCESS(f'Активировано товаров в розничном каталоге: {retail_count}')
        )
        
        # Активируем товары в оптовом каталоге
        # ВАЖНО: Товар должен быть активен, если есть остаток ИЛИ есть оптовая цена
        wholesale_products = Product.objects.filter(
            catalog_type='wholesale',
            is_active=False
        ).filter(
            Q(quantity__gt=0) | Q(wholesale_price__gt=0)
        )
        
        # Получаем ID товаров для обновления availability
        wholesale_product_ids = list(wholesale_products.values_list('id', flat=True))
        
        # Активируем товары
        wholesale_count = wholesale_products.update(is_active=True)
        
        # Обновляем availability правильно
        if wholesale_product_ids:
            # Товары с остатком - в наличии
            Product.objects.filter(
                id__in=wholesale_product_ids,
                quantity__gt=0
            ).update(availability='in_stock')
            
            # Товары без остатка, но с оптовой ценой - под заказ
            Product.objects.filter(
                id__in=wholesale_product_ids,
                quantity=0,
                wholesale_price__gt=0
            ).update(availability='order')
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
        
        # Статистика товаров, которые ДОЛЖНЫ быть активны, но не активны
        retail_should_be_active_but_not = Product.objects.filter(
            catalog_type='retail',
            is_active=False
        ).filter(
            Q(quantity__gt=0) | Q(price__gt=0)
        ).count()
        
        wholesale_should_be_active_but_not = Product.objects.filter(
            catalog_type='wholesale',
            is_active=False
        ).filter(
            Q(quantity__gt=0) | Q(wholesale_price__gt=0)
        ).count()
        
        # Товары, которые активны, но не должны быть
        retail_active_but_should_not = Product.objects.filter(
            catalog_type='retail',
            is_active=True
        ).filter(
            quantity=0,
            price=0
        ).count()
        
        wholesale_active_but_should_not = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True
        ).filter(
            quantity=0,
            wholesale_price=0
        ).count()
        
        self.stdout.write(f'\nСтатистика розничного каталога:')
        self.stdout.write(f'  Всего товаров: {retail_total}')
        self.stdout.write(f'  С остатком: {retail_with_stock}')
        self.stdout.write(f'  С ценой > 0: {retail_with_price}')
        self.stdout.write(f'  Активных: {retail_active}')
        # Ожидаемое количество активных: товары с остатком + товары с ценой (минус пересечение)
        retail_with_stock_or_price = Product.objects.filter(
            catalog_type='retail'
        ).filter(
            Q(quantity__gt=0) | Q(price__gt=0)
        ).count()
        self.stdout.write(f'  Должно быть активных (с остатком ИЛИ ценой): {retail_with_stock_or_price}')
        if retail_should_be_active_but_not > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  НЕ активных, но должны быть: {retail_should_be_active_but_not}')
            )
        if retail_active_but_should_not > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Активных, но не должны быть: {retail_active_but_should_not}')
            )
        
        wholesale_with_price = Product.objects.filter(catalog_type='wholesale', wholesale_price__gt=0).count()
        
        self.stdout.write(f'\nСтатистика оптового каталога:')
        self.stdout.write(f'  Всего товаров: {wholesale_total}')
        self.stdout.write(f'  С остатком: {wholesale_with_stock}')
        self.stdout.write(f'  С оптовой ценой > 0: {wholesale_with_price}')
        self.stdout.write(f'  Активных: {wholesale_active}')
        # Ожидаемое количество активных: товары с остатком + товары с оптовой ценой (минус пересечение)
        wholesale_with_stock_or_price = Product.objects.filter(
            catalog_type='wholesale'
        ).filter(
            Q(quantity__gt=0) | Q(wholesale_price__gt=0)
        ).count()
        self.stdout.write(f'  Должно быть активных (с остатком ИЛИ оптовой ценой): {wholesale_with_stock_or_price}')
        if wholesale_should_be_active_but_not > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  НЕ активных, но должны быть: {wholesale_should_be_active_but_not}')
            )
        if wholesale_active_but_should_not > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Активных, но не должны быть: {wholesale_active_but_should_not}')
            )
        
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
        
        # Оптовый каталог: товары без остатка и без оптовой цены
        wholesale_deactivated = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True
        ).filter(
            quantity=0,
            wholesale_price=0
        ).update(is_active=False)
        
        if wholesale_deactivated > 0:
            self.stdout.write(
                self.style.WARNING(f'Деактивировано товаров в оптовом каталоге (нет остатка и оптовой цены): {wholesale_deactivated}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nВсего активировано: {retail_count + wholesale_count}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Всего деактивировано: {retail_deactivated + wholesale_deactivated}')
        )
