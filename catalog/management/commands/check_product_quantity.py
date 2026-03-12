"""
Команда для проверки остатка конкретного товара и его обновления.
"""

from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Проверяет и обновляет остаток товара по артикулу или external_id'

    def add_arguments(self, parser):
        parser.add_argument(
            'identifier',
            type=str,
            help='Артикул или external_id товара',
        )
        parser.add_argument(
            '--quantity',
            type=int,
            help='Новое количество (если указано, обновит остаток)',
        )
        parser.add_argument(
            '--hide',
            action='store_true',
            help='Скрыть товар (is_active=False)',
        )
        parser.add_argument(
            '--show',
            action='store_true',
            help='Показать товар (is_active=True)',
        )

    def handle(self, *args, **options):
        identifier = options['identifier']
        new_quantity = options.get('quantity')
        hide = options.get('hide', False)
        show = options.get('show', False)
        
        # Ищем товар по артикулу или external_id
        product = Product.objects.filter(article=identifier).first()
        if not product:
            product = Product.objects.filter(external_id=identifier).first()
        
        if not product:
            self.stdout.write(
                self.style.ERROR(f'Товар с артикулом/external_id "{identifier}" не найден')
            )
            return
        
        self.stdout.write(f'Найден товар:')
        self.stdout.write(f'  ID: {product.id}')
        self.stdout.write(f'  Название: {product.name}')
        self.stdout.write(f'  Артикул: {product.article}')
        self.stdout.write(f'  External ID: {product.external_id}')
        self.stdout.write(f'  Каталог: {product.catalog_type}')
        self.stdout.write(f'  Текущий остаток: {product.quantity}')
        self.stdout.write(f'  Активен: {product.is_active}')
        self.stdout.write(f'  Наличие: {product.availability}')
        self.stdout.write(f'  Цена: {product.price if product.catalog_type == "retail" else product.wholesale_price}')
        
        # Обновляем количество, если указано
        if new_quantity is not None:
            old_quantity = product.quantity
            product.quantity = new_quantity
            
            # Обновляем активность на основе нового количества
            if new_quantity > 0:
                product.availability = 'in_stock'
                product.is_active = True
            else:
                product.availability = 'out_of_stock'
                product.is_active = False
            
            product.save(update_fields=['quantity', 'availability', 'is_active'])
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Обновлено количество: {old_quantity} → {new_quantity}'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Активность: {"Активен" if product.is_active else "Скрыт"}'
                )
            )
        
        # Скрываем товар, если указано
        if hide:
            product.is_active = False
            product.availability = 'out_of_stock'
            product.save(update_fields=['is_active', 'availability'])
            self.stdout.write(
                self.style.WARNING(f'\n✓ Товар скрыт')
            )
        
        # Показываем товар, если указано
        if show:
            if product.quantity > 0:
                product.is_active = True
                product.availability = 'in_stock'
                product.save(update_fields=['is_active', 'availability'])
                self.stdout.write(
                    self.style.SUCCESS(f'\n✓ Товар активирован (остаток: {product.quantity})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'\n⚠ Нельзя активировать товар с остатком = 0')
                )
