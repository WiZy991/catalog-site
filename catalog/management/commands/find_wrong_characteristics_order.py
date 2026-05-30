"""
Находит товары, у которых блок «Применимость и характеристики»
отображается не в каноническом порядке (до сортировки на карточке).

Канонический порядок:
  Номер → OEM → Применимо для моделей → Применимо для двигателей
  → Кросс-номера → Характеристика → (Напряжение)
"""
from django.core.management.base import BaseCommand

import catalog.views as catalog_views
from catalog.models import Product
from catalog.services import display_characteristics_order_is_canonical
from catalog.views import ProductView


def build_display_characteristics(product, *, apply_sort=False):
    """Собирает поля карточки так же, как ProductView (опционально с сортировкой)."""
    view = ProductView()
    view.object = product
    original_sort = catalog_views.sort_display_characteristics
    if not apply_sort:
        catalog_views.sort_display_characteristics = lambda chars: list(chars)
    try:
        context = view.get_context_data()
        return list(context.get('characteristics') or [])
    finally:
        catalog_views.sort_display_characteristics = original_sort


class Command(BaseCommand):
    help = (
        'Список товаров с неканоническим порядком полей '
        '«Применимость и характеристики»'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--catalog',
            choices=('retail', 'wholesale', 'all'),
            default='retail',
            help='Какой каталог проверять (по умолчанию: retail)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Ограничить число проверяемых товаров (0 = без ограничения)',
        )
        parser.add_argument(
            '--export',
            type=str,
            default='',
            help='Путь к CSV-файлу для выгрузки (id;article;name;field_order)',
        )

    def handle(self, *args, **options):
        qs = Product.objects.filter(is_active=True)
        catalog = options['catalog']
        if catalog != 'all':
            qs = qs.filter(catalog_type=catalog)
        qs = qs.order_by('id')
        limit = options['limit']
        if limit:
            qs = qs[:limit]

        total = qs.count()
        wrong = []
        self.stdout.write(f'Проверяем {total} товаров (catalog={catalog})...')

        for product in qs.iterator(chunk_size=200):
            chars = build_display_characteristics(product, apply_sort=False)
            if not chars:
                continue
            if not display_characteristics_order_is_canonical(chars):
                keys = [k for k, _ in chars]
                wrong.append((product, keys))

        self.stdout.write(self.style.WARNING(
            f'Найдено товаров с неправильным порядком: {len(wrong)} из {total}'
        ))

        export_path = (options.get('export') or '').strip()
        if export_path:
            import csv
            with open(export_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['id', 'article', 'external_id', 'name', 'field_order'])
                for product, keys in wrong:
                    writer.writerow([
                        product.id,
                        product.article or '',
                        product.external_id or '',
                        product.name or '',
                        ' | '.join(keys),
                    ])
            self.stdout.write(self.style.SUCCESS(f'CSV: {export_path}'))

        show_limit = 50
        for product, keys in wrong[:show_limit]:
            self.stdout.write(
                f'  id={product.id} art={product.article!r} '
                f'order={" → ".join(keys)}'
            )
        if len(wrong) > show_limit:
            self.stdout.write(f'  ... и ещё {len(wrong) - show_limit}')
