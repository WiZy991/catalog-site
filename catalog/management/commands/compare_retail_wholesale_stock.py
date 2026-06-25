"""
Находит расхождение «в наличии» между розницей и оптом.
"""
from django.core.management.base import BaseCommand

from catalog.models import Product


class Command(BaseCommand):
    help = 'Сравнивает retail и wholesale: кто лишний/пропавший «в наличии»'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            choices=['stock', 'active', 'show'],
            default='stock',
            help='stock = is_active + quantity>0 (по умолчанию)',
        )

    def handle(self, *args, **options):
        mode = options['mode']
        retail_qs, wholesale_qs, label = self._querysets(mode)

        retail_count = retail_qs.count()
        wholesale_count = wholesale_qs.count()

        self.stdout.write('=' * 72)
        self.stdout.write(f'Сравнение retail / wholesale — {label}')
        self.stdout.write('=' * 72)
        self.stdout.write(f'  Розница:  {retail_count}')
        self.stdout.write(f'  Опт:      {wholesale_count}')
        diff = wholesale_count - retail_count
        if diff == 0:
            self.stdout.write(self.style.SUCCESS('  Разница: 0'))
        else:
            self.stdout.write(self.style.WARNING(f'  Разница (опт − розница): {diff:+d}'))
        self.stdout.write()

        retail_by_art = {self._key(p): p for p in retail_qs if self._key(p)}
        wholesale_by_art = {self._key(p): p for p in wholesale_qs if self._key(p)}

        only_wholesale = set(wholesale_by_art) - set(retail_by_art)
        only_retail = set(retail_by_art) - set(wholesale_by_art)

        if only_wholesale:
            self.stdout.write(self.style.WARNING(f'Только в ОПТЕ ({len(only_wholesale)}):'))
            for k in sorted(only_wholesale):
                self._print_product(wholesale_by_art[k])
            self.stdout.write()

        if only_retail:
            self.stdout.write(self.style.WARNING(f'Только в РОЗНИЦЕ ({len(only_retail)}):'))
            for k in sorted(only_retail):
                self._print_product(retail_by_art[k])
            self.stdout.write()

        common = set(retail_by_art) & set(wholesale_by_art)
        mismatched = [
            (k, retail_by_art[k], wholesale_by_art[k])
            for k in common
            if retail_by_art[k].quantity != wholesale_by_art[k].quantity
            or retail_by_art[k].is_active != wholesale_by_art[k].is_active
        ]
        if mismatched:
            self.stdout.write(self.style.WARNING(f'Один артикул, разный qty/active ({len(mismatched)}):'))
            for k, r, w in mismatched:
                self.stdout.write(
                    f'  [{k}] retail pk={r.pk} qty={r.quantity} active={r.is_active} | '
                    f'wholesale pk={w.pk} qty={w.quantity} active={w.is_active}'
                )
            self.stdout.write()

        r_total = Product.objects.filter(catalog_type='retail').count()
        w_total = Product.objects.filter(catalog_type='wholesale').count()
        self.stdout.write(f'Всего строк в БД: retail={r_total}, wholesale={w_total}, diff={w_total - r_total:+d}')
        self.stdout.write('=' * 72)

    def _querysets(self, mode):
        if mode == 'active':
            label = 'is_active=True'
            return (
                Product.objects.filter(catalog_type='retail', is_active=True),
                Product.objects.filter(catalog_type='wholesale', is_active=True),
                label,
            )
        if mode == 'show':
            label = 'active + qty>0 + цена + категория'
            return (
                Product.objects.filter(
                    catalog_type='retail', is_active=True, quantity__gt=0,
                    price__gt=0, category__isnull=False, category__is_active=True,
                ),
                Product.objects.filter(
                    catalog_type='wholesale', is_active=True, quantity__gt=0,
                    wholesale_price__gt=0, category__isnull=False, category__is_active=True,
                ),
                label,
            )
        label = 'is_active + quantity>0'
        return (
            Product.objects.filter(catalog_type='retail', is_active=True, quantity__gt=0),
            Product.objects.filter(catalog_type='wholesale', is_active=True, quantity__gt=0),
            label,
        )

    @staticmethod
    def _key(product):
        art = (product.article or product.supplier_article or '').strip().upper()
        if art:
            return art
        eid = (product.external_id or '').strip()
        return f'id:{eid}' if eid else f'pk:{product.pk}'

    def _print_product(self, p):
        price = p.wholesale_price if p.catalog_type == 'wholesale' else p.price
        self.stdout.write(
            f'  pk={p.pk} catalog={p.catalog_type} art={p.article!r} ext={p.external_id!r} '
            f'qty={p.quantity} active={p.is_active} price={price} | {p.name[:60]}'
        )
