"""
Активирует товары «нет в наличии» для отображения на сайте (ч/б, без корзины).

Типичный случай после старой синхронизации 1С:
  is_active=False, availability=out_of_stock, quantity>0 (устаревший остаток).

Исправление: quantity=0, is_active=True — видно на сайте, не уходит на Farpost.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from catalog.models import Product


class Command(BaseCommand):
    help = 'Показывает на сайте скрытые товары без остатка (qty=0, active=True)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать статистику, без изменений',
        )
        parser.add_argument(
            '--catalog-type',
            choices=['retail', 'wholesale', 'all'],
            default='all',
        )
        parser.add_argument(
            '--mode',
            choices=['stale', 'strict', 'broad'],
            default='stale',
            help=(
                'stale (по умолчанию) — скрытые out_of_stock с устаревшим qty>0; '
                'strict — скрытые с qty=0 и external_id; '
                'broad — все скрытые с qty=0'
            ),
        )

    def _base_qs(self, catalog_type):
        qs = Product.objects.all()
        if catalog_type != 'all':
            qs = qs.filter(catalog_type=catalog_type)
        return qs

    def _print_breakdown(self, catalog_type):
        base = self._base_qs(catalog_type)
        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write(f'СТАТИСТИКА (catalog_type={catalog_type})')
        self.stdout.write('=' * 70)

        stale_hidden = base.filter(
            is_active=False,
            availability='out_of_stock',
            quantity__gt=0,
        )
        self.stdout.write(
            f'Скрытые с устаревшим остатком (inactive, out_of_stock, qty>0): '
            f'{stale_hidden.count()}'
        )

        zero_qty = base.filter(quantity=0)
        self.stdout.write(f'Товаров с quantity=0: {zero_qty.count()}')
        self.stdout.write(
            f'  — видимых (active=True): {zero_qty.filter(is_active=True).count()}'
        )
        self.stdout.write(
            f'  — скрытых (active=False): {zero_qty.filter(is_active=False).count()}'
        )

        hidden = base.filter(is_active=False)
        self.stdout.write(f'Всего скрытых (inactive): {hidden.count()}')
        for row in hidden.values('availability').annotate(c=Count('id')).order_by('-c'):
            self.stdout.write(f"  availability={row['availability']}: {row['c']}")
        self.stdout.write('=' * 70)

    def _get_target_qs(self, catalog_type, mode):
        if catalog_type != 'all':
            qs = Product.objects.filter(catalog_type=catalog_type)
        else:
            qs = Product.objects.all()

        if mode == 'stale':
            return qs.filter(
                is_active=False,
                availability='out_of_stock',
                quantity__gt=0,
            ).exclude(category__isnull=True)

        filters = {'quantity': 0, 'is_active': False}
        if catalog_type != 'all':
            filters['catalog_type'] = catalog_type
        qs = Product.objects.filter(**filters)

        if mode == 'strict':
            qs = qs.filter(availability='out_of_stock').exclude(
                Q(external_id__isnull=True) | Q(external_id='')
            )
        else:
            qs = qs.exclude(category__isnull=True)

        return qs

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']
        mode = options['mode']

        self._print_breakdown(catalog_type)

        qs = self._get_target_qs(catalog_type, mode)
        count = qs.count()

        self.stdout.write('')
        self.stdout.write(f'Режим: {mode}')
        self.stdout.write(f'К исправлению: {count}')

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Нет товаров под выбранные критерии.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('dry-run: изменения не применены'))
            for p in qs[:10]:
                self.stdout.write(
                    f'  id={p.pk} [{p.catalog_type}] qty={p.quantity} '
                    f'active={p.is_active} avail={p.availability} | {p.name[:50]}'
                )
            if count > 10:
                self.stdout.write(f'  ... и ещё {count - 10}')
            return

        if mode == 'stale':
            updated = qs.update(
                quantity=0,
                is_active=True,
                availability='out_of_stock',
            )
        else:
            updated = qs.update(is_active=True)

        self.stdout.write(self.style.SUCCESS(f'Исправлено товаров: {updated}'))
