"""
Команда для массового обновления остатков товаров по артикулу.
"""

from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Обновляет остаток товара до 0 и скрывает его'

    def add_arguments(self, parser):
        parser.add_argument(
            'article',
            type=str,
            help='Артикул товара',
        )

    def handle(self, *args, **options):
        article = options['article']
        
        # Ищем товары по артикулу во ВСЕХ каталогах
        products = Product.objects.filter(article=article)
        
        if not products.exists():
            self.stdout.write(
                self.style.ERROR(f'Товар с артикулом "{article}" не найден')
            )
            return
        
        updated_count = 0
        for product in products:
            old_quantity = product.quantity
            old_is_active = product.is_active
            old_availability = product.availability
            
            # Обновляем остаток до 0
            product.quantity = 0
            product.is_active = False
            product.availability = 'out_of_stock'
            
            product.save(update_fields=['quantity', 'is_active', 'availability'])
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Обновлен товар в каталоге {product.catalog_type}: '
                    f'остаток {old_quantity} → 0, '
                    f'активен {old_is_active} → False, '
                    f'наличие {old_availability} → out_of_stock'
                )
            )
            updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Всего обновлено товаров: {updated_count}')
        )
