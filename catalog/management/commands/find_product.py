"""Поиск товара в БД по артикулу/OEM (диагностика видимости на сайте)."""
from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.models import Product
from catalog.search_utils import product_search_word_q


class Command(BaseCommand):
    help = 'Найти товар в БД по артикулу/OEM и показать, почему он не виден на сайте'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='Артикул, OEM или часть названия')

    def handle(self, *args, **options):
        query = options['query'].strip()
        if not query:
            self.stdout.write(self.style.ERROR('Укажите артикул или OEM'))
            return

        self.stdout.write(f'Поиск: «{query}»')
        self.stdout.write('=' * 72)

        # Все записи в БД (включая скрытые)
        all_matches = Product.objects.filter(product_search_word_q(query)).distinct()
        self.stdout.write(f'Всего в БД (retail + wholesale): {all_matches.count()}')

        if not all_matches.exists():
            self.stdout.write(self.style.ERROR(
                'Товар не найден в базе сайта. Нужен обмен import.xml / offers.xml из 1С.'
            ))
            return

        for p in all_matches[:20]:
            visible_retail = (
                p.catalog_type == 'retail'
                and p.is_active
                and p.quantity > 0
                and p.availability == 'in_stock'
            )
            visible_wholesale = p.catalog_type == 'wholesale' and p.is_active
            purchasable = p.is_purchasable
            reasons = []
            if not p.is_active:
                reasons.append('is_active=False (скрыт обменом 1С)')
            if p.quantity == 0 and p.is_active:
                reasons.append('qty=0 — виден ч/б, в корзину нельзя')
            elif p.quantity > 0 and not p.is_active:
                reasons.append(f'устаревший остаток qty={p.quantity}')

            if visible_retail:
                status = self.style.SUCCESS('ВИДЕН в рознице (в наличии)')
            elif p.catalog_type == 'retail' and p.is_active:
                status = self.style.WARNING('НЕ ВИДЕН в рознице (нет в наличии)')
            elif visible_wholesale:
                status = self.style.SUCCESS('ВИДЕН в опте')
            else:
                status = self.style.WARNING('НЕ ВИДЕН')
            self.stdout.write('')
            self.stdout.write(f'[{p.catalog_type}] id={p.pk} {status}')
            self.stdout.write(f'  name: {p.name[:70]}')
            self.stdout.write(f'  article={p.article or "-"} supplier_article={p.supplier_article or "-"}')
            self.stdout.write(
                f'  qty={p.quantity} active={p.is_active} avail={p.availability} '
                f'purchasable={purchasable}'
            )
            if reasons:
                self.stdout.write(f'  причина: {"; ".join(reasons)}')

        retail_visible = Product.for_site_catalog('retail').filter(
            pk__in=all_matches.values_list('pk', flat=True)
        ).count()
        wholesale_visible = Product.for_site_catalog('wholesale').filter(
            pk__in=all_matches.values_list('pk', flat=True)
        ).count()
        self.stdout.write('')
        self.stdout.write('=' * 72)
        if retail_visible:
            self.stdout.write(self.style.SUCCESS(f'Видимых в рознице: {retail_visible}'))
        else:
            stale = all_matches.filter(
                catalog_type='retail', is_active=False, availability='out_of_stock', quantity__gt=0
            ).count()
            self.stdout.write(self.style.WARNING('В рознице на сайте не отображается.'))
            if stale:
                self.stdout.write(
                    f'  {stale} записей со «старым» остатком — выполните:\n'
                    '  python manage.py reactivate_out_of_stock_products'
                )
        if wholesale_visible:
            self.stdout.write(self.style.SUCCESS(f'Видимых в опте: {wholesale_visible}'))
        elif all_matches.filter(catalog_type='wholesale').exists():
            self.stdout.write(self.style.WARNING('В опте на сайте не отображается.'))
