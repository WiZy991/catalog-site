"""
Очищает поле applicability у оптовых товаров.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Очищает поле applicability у оптовых товаров'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет очищено, без фактического изменения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим все оптовые товары с заполненным полем applicability
        wholesale_products = Product.objects.filter(
            catalog_type='wholesale',
            applicability__isnull=False
        ).exclude(applicability='')
        
        total_count = wholesale_products.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ Нет оптовых товаров с заполненным полем applicability')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Будет очищено поле applicability у {total_count} оптовых товаров:'
                )
            )
            for product in wholesale_products[:20]:  # Показываем первые 20
                self.stdout.write(
                    f'  - {product.name} (ID: {product.pk}, Артикул: {product.article})'
                )
            if total_count > 20:
                self.stdout.write(f'  ... и ещё {total_count - 20} товаров')
            self.stdout.write(
                self.style.WARNING(
                    '\nЗапустите команду без --dry-run для фактической очистки'
                )
            )
        else:
            updated = wholesale_products.update(applicability='')
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Готово! Очищено поле applicability у {updated} оптовых товаров'
                )
            )
