"""
Сверка offers.xml с витриной сайта.

Находит позиции из 1С (Количество > 0), которые не видны на сайте
(catalog_type=retail, is_active=True, quantity > 0).
"""
import csv
import os
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.models import Product
from catalog.offers_parse import iter_offers_from_file


class Command(BaseCommand):
    help = 'Сверяет offers.xml с витриной и находит скрытые товары'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Путь к offers.xml (или xml_offers.txt)',
        )
        parser.add_argument(
            '--oem',
            action='append',
            default=[],
            help='Проверить конкретный OEM/артикул (можно несколько раз)',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Активировать hidden/zero_qty для позиций из текущего XML',
        )
        parser.add_argument(
            '--csv',
            type=str,
            default='',
            help='Путь к CSV-отчёту (по умолчанию reports/offers_reconcile_YYYYMMDD.csv)',
        )

    def handle(self, *args, **options):
        file_path = options['file']
        if not os.path.isabs(file_path):
            file_path = os.path.join(settings.BASE_DIR, file_path)
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Файл не найден: {file_path}'))
            return

        oem_filters = [o.strip() for o in options['oem'] if o and o.strip()]
        apply_fix = options['apply']

        self.stdout.write('=' * 80)
        self.stdout.write('СВЕРКА OFFERS.XML С ВИТРИНОЙ')
        self.stdout.write('=' * 80)
        self.stdout.write(f'Файл: {file_path}')
        self.stdout.write()

        offers_in_stock = []
        for offer in iter_offers_from_file(file_path):
            if oem_filters:
                keys_upper = {k.upper() for k in offer['article_keys']}
                if not keys_upper.intersection({o.upper() for o in oem_filters}):
                    continue
            if offer['quantity'] > 0:
                offers_in_stock.append(offer)

        if oem_filters and not offers_in_stock:
            self.stdout.write(self.style.WARNING('Предложения с указанными OEM не найдены в файле.'))
            return

        visible_on_site = Product.objects.filter(
            catalog_type='retail',
            is_active=True,
            quantity__gt=0,
        )
        visible_count = visible_on_site.count()
        visible_external_ids = set(
            visible_on_site.exclude(external_id__isnull=True)
            .exclude(external_id='')
            .values_list('external_id', flat=True)
        )

        rows = []
        stats = {'visible': 0, 'hidden': 0, 'zero_qty': 0, 'missing': 0}
        matched_product_ids = set()
        applied = 0

        for offer in offers_in_stock:
            product, match_by = self._find_retail_product(offer)
            status = self._classify(offer, product)
            stats[status] = stats.get(status, 0) + 1

            if product:
                matched_product_ids.add(product.pk)

            row = {
                'status': status,
                'external_id': offer['external_id'],
                'oem': offer['article_keys'][0] if offer['article_keys'] else '',
                'article_keys': '; '.join(offer['article_keys']),
                'xml_qty': offer['quantity'],
                'xml_price': offer['retail_price'] or 0,
                'name': offer['name'][:200],
                'product_id': product.pk if product else '',
                'db_external_id': product.external_id if product else '',
                'db_article': product.article if product else '',
                'db_qty': product.quantity if product else '',
                'db_active': product.is_active if product else '',
                'match_by': match_by,
            }
            rows.append(row)

            if apply_fix and status in ('hidden', 'zero_qty') and product:
                product.quantity = offer['quantity']
                product.is_active = True
                product.availability = 'in_stock'
                if offer['external_id'] and product.external_id != offer['external_id']:
                    product.external_id = offer['external_id']
                update_fields = ['quantity', 'is_active', 'availability']
                if offer['external_id']:
                    update_fields.append('external_id')
                if offer['retail_price'] is not None:
                    product.price = offer['retail_price']
                    update_fields.append('price')
                product.save(update_fields=update_fields)
                applied += 1

        xml_count = len(offers_in_stock)
        gap = xml_count - stats['visible']

        extra_qs = visible_on_site.exclude(pk__in=matched_product_ids)
        if oem_filters:
            extra_qs = extra_qs.none()
        extra_count = extra_qs.count()

        csv_path = options['csv'] or os.path.join(
            settings.BASE_DIR,
            'reports',
            f'offers_reconcile_{date.today().isoformat()}.csv',
        )
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        self._write_csv(csv_path, rows, extra_qs)

        self.stdout.write(f'XML qty>0: {xml_count}')
        self.stdout.write(f'Видно на сайте (retail active qty>0): {visible_count}')
        self.stdout.write(f'  visible (совпали и на витрине): {stats["visible"]}')
        self.stdout.write(self.style.WARNING(f'  hidden (в БД, is_active=False): {stats["hidden"]}'))
        self.stdout.write(self.style.WARNING(f'  zero_qty (в БД qty=0): {stats["zero_qty"]}'))
        self.stdout.write(self.style.ERROR(f'  missing (нет в БД): {stats["missing"]}'))
        self.stdout.write(f'GAP (должны быть на сайте, но не visible): {gap}')
        self.stdout.write(f'Extra на сайте (не сопоставлены с XML): {extra_count}')
        self.stdout.write()
        self.stdout.write(f'CSV: {csv_path}')

        if stats['hidden'] or stats['zero_qty'] or stats['missing']:
            self.stdout.write()
            self.stdout.write('Примеры проблемных позиций:')
            shown = 0
            for row in rows:
                if row['status'] in ('hidden', 'zero_qty', 'missing'):
                    self.stdout.write(
                        f"  [{row['status']}] {row['oem'] or row['article_keys'][:40]} "
                        f"| {row['name'][:60]} | xml_qty={row['xml_qty']} "
                        f"| product_id={row['product_id']}"
                    )
                    shown += 1
                    if shown >= 20:
                        break

        if apply_fix:
            self.stdout.write()
            self.stdout.write(self.style.SUCCESS(f'--apply: обновлено карточек: {applied}'))
        elif gap > 0:
            self.stdout.write()
            self.stdout.write('Для исправления: python manage.py reconcile_offers_site --file ... --apply')

        self.stdout.write('=' * 80)

    def _find_retail_product(self, offer):
        eid = offer['external_id']
        if eid:
            p = Product.objects.filter(catalog_type='retail', external_id=eid).first()
            if p:
                return p, 'external_id'

        for key in offer['article_keys']:
            p = Product.objects.filter(
                catalog_type='retail',
            ).filter(
                Q(article__iexact=key) | Q(supplier_article__iexact=key)
            ).first()
            if p:
                return p, f'article:{key}'

        for oem in offer['oem_keys'] or offer['article_keys']:
            p = Product.objects.filter(catalog_type='retail').filter(
                Q(name__icontains=oem)
                | Q(cross_numbers__icontains=oem)
                | Q(characteristics__icontains=oem)
            ).first()
            if p:
                return p, f'oem:{oem}'

        return None, ''

    def _classify(self, offer, product):
        if product is None:
            return 'missing'
        if product.is_active and product.quantity > 0:
            return 'visible'
        if product.quantity > 0 and not product.is_active:
            return 'hidden'
        return 'zero_qty'

    def _write_csv(self, csv_path, rows, extra_qs):
        fieldnames = [
            'status', 'external_id', 'oem', 'article_keys', 'xml_qty', 'xml_price',
            'name', 'product_id', 'db_external_id', 'db_article', 'db_qty',
            'db_active', 'match_by',
        ]
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            for p in extra_qs[:500]:
                writer.writerow({
                    'status': 'extra',
                    'external_id': p.external_id or '',
                    'oem': p.article or '',
                    'article_keys': p.supplier_article or '',
                    'xml_qty': '',
                    'xml_price': '',
                    'name': p.name[:200],
                    'product_id': p.pk,
                    'db_external_id': p.external_id or '',
                    'db_article': p.article or '',
                    'db_qty': p.quantity,
                    'db_active': p.is_active,
                    'match_by': 'site_only',
                })
