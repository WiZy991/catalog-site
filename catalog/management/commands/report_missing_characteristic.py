"""
Товары, у которых в 1С/базе есть «Характеристика», но на карточке она могла не показаться
(или наоборот — нет ни в базе, ни в fallback).
"""
from django.core.management.base import BaseCommand

from catalog.models import Product
from catalog.services import get_product_characteristic_display_value


def _raw_has_characteristic_line(product) -> bool:
    text = str(product.characteristics or '')
    for line in text.split('\n'):
        if line.strip().lower().startswith('характеристика:'):
            val = line.split(':', 1)[-1].strip()
            if val:
                return True
    return False


def _display_has_characteristic(product) -> bool:
    for key, val in product.get_display_characteristics_list():
        if str(key).strip().lower() in ('характеристика', 'характеристики', 'размер', 'size'):
            if str(val).strip():
                return True
    return False


class Command(BaseCommand):
    help = 'Отчёт: где есть/нет значение «Характеристика» (R, F/R, RH/LH и т.д.)'

    def add_arguments(self, parser):
        parser.add_argument('--catalog', choices=('retail', 'wholesale', 'all'), default='retail')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--export', type=str, default='')

    def handle(self, *args, **options):
        qs = Product.objects.filter(is_active=True)
        if options['catalog'] != 'all':
            qs = qs.filter(catalog_type=options['catalog'])
        if options['limit']:
            qs = qs[: options['limit']]

        missing_on_display = []
        has_fallback_only = []
        ok = 0

        for product in qs.iterator(chunk_size=200):
            raw = _raw_has_characteristic_line(product)
            display = _display_has_characteristic(product)
            fallback = get_product_characteristic_display_value(product)

            if display:
                ok += 1
                continue

            if raw or fallback:
                entry = (product, 'в базе' if raw else 'только fallback', fallback or '')
                if raw and not display:
                    missing_on_display.append(entry)
                elif fallback and not raw:
                    has_fallback_only.append(entry)
            else:
                missing_on_display.append((product, 'нет данных', ''))

        total = qs.count() if not options['limit'] else min(options['limit'], qs.count())
        self.stdout.write(f'Проверено: {total}')
        self.stdout.write(self.style.SUCCESS(f'С «Характеристика» на карточке: {ok}'))
        self.stdout.write(self.style.WARNING(
            f'Без строки на карточке (но есть в базе/fallback): {len(missing_on_display)}'
        ))
        self.stdout.write(f'Только fallback (нет строки в characteristics): {len(has_fallback_only)}')

        rows = missing_on_display + has_fallback_only
        if options['export'] and rows:
            import csv
            with open(options['export'], 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(['id', 'article', 'name', 'источник', 'значение'])
                for product, src, val in rows[:5000]:
                    w.writerow([product.id, product.article, product.name, src, val])
            self.stdout.write(self.style.SUCCESS(f'CSV: {options["export"]}'))

        for product, src, val in rows[:30]:
            self.stdout.write(f'  id={product.id} {src} val={val!r} art={product.article!r}')
