"""
Активирует товары с нулевым остатком для отображения на сайте.
Запускать один раз после включения показа отсутствующих товаров.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Активирует товары с quantity=0 для показа на сайте (не влияет на Farpost)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать количество без изменений',
        )
        parser.add_argument(
            '--catalog-type',
            choices=['retail', 'wholesale', 'all'],
            default='all',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']

        filters = {
            'quantity': 0,
            'availability': 'out_of_stock',
            'is_active': False,
        }
        if catalog_type != 'all':
            filters['catalog_type'] = catalog_type

        qs = Product.objects.filter(**filters).exclude(external_id__isnull=True).exclude(external_id='')
        count = qs.count()

        self.stdout.write(f'Найдено скрытых товаров с нулевым остатком: {count}')
        if dry_run or count == 0:
            return

        updated = qs.update(is_active=True)
        self.stdout.write(self.style.SUCCESS(f'Активировано товаров: {updated}'))
