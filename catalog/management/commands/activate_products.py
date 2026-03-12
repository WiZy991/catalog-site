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
        # ВАЖНО: Товары активируются ТОЛЬКО если есть остаток > 0 (не по цене)
        retail_should_be_active = Product.objects.filter(
            catalog_type='retail',
            is_active=False,
            quantity__gt=0  # ТОЛЬКО товары с остатком
        )
        
        retail_should_be_active_count = retail_should_be_active.count()
        
        wholesale_should_be_active = Product.objects.filter(
            catalog_type='wholesale',
            is_active=False,
            quantity__gt=0  # ТОЛЬКО товары с остатком
        )
        
        wholesale_should_be_active_count = wholesale_should_be_active.count()
        
        self.stdout.write(f'Найдено товаров для активации (только с остатком > 0):')
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
        # ВАЖНО: Товар должен быть активен ТОЛЬКО если есть остаток > 0 (не по цене)
        retail_products = Product.objects.filter(
            catalog_type='retail',
            is_active=False,
            quantity__gt=0  # ТОЛЬКО товары с остатком
        )
        
        retail_count = retail_products.update(
            is_active=True,
            availability='in_stock'
        )
        self.stdout.write(
            self.style.SUCCESS(f'Активировано товаров в розничном каталоге: {retail_count}')
        )
        
        # Активируем товары в оптовом каталоге
        # ВАЖНО: Товар должен быть активен ТОЛЬКО если есть остаток > 0 (не по цене)
        wholesale_products = Product.objects.filter(
            catalog_type='wholesale',
            is_active=False,
            quantity__gt=0  # ТОЛЬКО товары с остатком
        )
        
        wholesale_count = wholesale_products.update(
            is_active=True,
            availability='in_stock'
        )
        self.stdout.write(
            self.style.SUCCESS(f'Активировано товаров в оптовом каталоге: {wholesale_count}')
        )
        
        # Деактивируем товары без остатка (даже если есть цена)
        retail_to_deactivate = Product.objects.filter(
            catalog_type='retail',
            is_active=True,
            quantity=0
        )
        retail_deactivated = retail_to_deactivate.update(
            is_active=False,
            availability='out_of_stock'
        )
        if retail_deactivated > 0:
            self.stdout.write(
                self.style.WARNING(f'Деактивировано товаров в розничном каталоге без остатка: {retail_deactivated}')
            )
        
        wholesale_to_deactivate = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True,
            quantity=0
        )
        wholesale_deactivated = wholesale_to_deactivate.update(
            is_active=False,
            availability='out_of_stock'
        )
        if wholesale_deactivated > 0:
            self.stdout.write(
                self.style.WARNING(f'Деактивировано товаров в оптовом каталоге без остатка: {wholesale_deactivated}')
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
        # ВАЖНО: Товары должны быть активны ТОЛЬКО если есть остаток > 0
        retail_should_be_active_but_not = Product.objects.filter(
            catalog_type='retail',
            is_active=False,
            quantity__gt=0  # ТОЛЬКО товары с остатком
        ).count()
        
        wholesale_should_be_active_but_not = Product.objects.filter(
            catalog_type='wholesale',
            is_active=False,
            quantity__gt=0  # ТОЛЬКО товары с остатком
        ).count()
        
        # Товары, которые активны, но не должны быть (без остатка)
        retail_active_but_should_not = Product.objects.filter(
            catalog_type='retail',
            is_active=True,
            quantity=0  # Без остатка - должны быть скрыты
        ).count()
        
        wholesale_active_but_should_not = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True,
            quantity=0  # Без остатка - должны быть скрыты
        ).count()
        
        self.stdout.write(f'\nСтатистика розничного каталога:')
        self.stdout.write(f'  Всего товаров: {retail_total}')
        self.stdout.write(f'  С остатком: {retail_with_stock}')
        self.stdout.write(f'  С ценой > 0: {retail_with_price}')
        self.stdout.write(f'  Активных: {retail_active}')
        # Ожидаемое количество активных: ТОЛЬКО товары с остатком > 0
        self.stdout.write(f'  Должно быть активных (только с остатком > 0): {retail_with_stock}')
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
        # Ожидаемое количество активных: ТОЛЬКО товары с остатком > 0
        self.stdout.write(f'  Должно быть активных (только с остатком > 0): {wholesale_with_stock}')
        if wholesale_should_be_active_but_not > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  НЕ активных, но должны быть: {wholesale_should_be_active_but_not}')
            )
        if wholesale_active_but_should_not > 0:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Активных, но не должны быть: {wholesale_active_but_should_not}')
            )
        
        # Деактивируем товары, которые не должны быть активны
        # ВАЖНО: Товары без остатка должны быть скрыты независимо от цены
        # Розничный каталог: товары без остатка (даже если есть цена)
        retail_to_deactivate = Product.objects.filter(
            catalog_type='retail',
            is_active=True,
            quantity=0  # Без остатка - скрываем независимо от цены
        )
        retail_deactivated = retail_to_deactivate.update(
            is_active=False,
            availability='out_of_stock'
        )
        
        if retail_deactivated > 0:
            self.stdout.write(
                self.style.WARNING(f'Деактивировано товаров в розничном каталоге без остатка: {retail_deactivated}')
            )
        
        # Оптовый каталог: товары без остатка (даже если есть оптовая цена)
        wholesale_to_deactivate = Product.objects.filter(
            catalog_type='wholesale',
            is_active=True,
            quantity=0  # Без остатка - скрываем независимо от цены
        )
        wholesale_deactivated = wholesale_to_deactivate.update(
            is_active=False,
            availability='out_of_stock'
        )
        
        if wholesale_deactivated > 0:
            self.stdout.write(
                self.style.WARNING(f'Деактивировано товаров в оптовом каталоге без остатка: {wholesale_deactivated}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nВсего активировано: {retail_count + wholesale_count}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Всего деактивировано: {retail_deactivated + wholesale_deactivated}')
        )
