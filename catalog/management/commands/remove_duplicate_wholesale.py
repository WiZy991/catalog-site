"""
Находит и деактивирует дубликаты товаров (одинаковый артикул) в оптовом и/или розничном каталогах.
Оставляет товар с наиболее полными данными.
Использование:
  python manage.py remove_duplicate_wholesale --dry-run               # только оптовый
  python manage.py remove_duplicate_wholesale --retail --dry-run      # только розничный
  python manage.py remove_duplicate_wholesale --all --dry-run         # оба каталога
  python manage.py remove_duplicate_wholesale --all                   # оба, деактивировать
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from catalog.models import Product


class Command(BaseCommand):
    help = 'Деактивирует дубликаты товаров, оставляя наиболее полный'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать, не деактивировать')
        parser.add_argument('--retail', action='store_true', help='Обрабатывать розничный каталог вместо оптового')
        parser.add_argument('--all', action='store_true', dest='all_catalogs', help='Обрабатывать оба каталога')

    def _completeness(self, product):
        score = 0
        score += len(product.name or '')
        score += len(product.characteristics or '') * 2
        score += len(product.applicability or '')
        score += len(product.cross_numbers or '')
        if product.quantity and product.quantity > 0:
            score += 500
        if product.wholesale_price and product.wholesale_price > 0:
            score += 500
        if product.images.exists():
            score += 1000
        return score

    def _process_catalog(self, catalog_type, dry_run):
        label = 'розничный' if catalog_type == 'retail' else 'оптовый'
        self.stdout.write(f'\n=== {label.upper()} каталог ({catalog_type}) ===')

        dupes = (
            Product.objects.filter(is_active=True, catalog_type=catalog_type)
            .exclude(article='')
            .exclude(article__isnull=True)
            .values('article')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
            .order_by('-cnt')
        )

        total_articles = dupes.count()
        if total_articles == 0:
            self.stdout.write(self.style.SUCCESS(f'Дубликатов в {label} каталоге не найдено.'))
            return 0

        self.stdout.write(f'Найдено артикулов с дубликатами: {total_articles}')
        to_deactivate = []

        for dupe in dupes:
            article = dupe['article']
            products = list(
                Product.objects.filter(
                    article=article, catalog_type=catalog_type, is_active=True
                ).order_by('id')
            )
            scored = [(self._completeness(p), p) for p in products]
            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[0][1]
            rest = [s[1] for s in scored[1:]]

            if dry_run and len(products) <= 5:
                self.stdout.write(f'\n  article={article} ({len(products)} шт.) — оставляем ID={best.id}')
                for p in rest:
                    self.stdout.write(f'    удалим ID={p.id}: {p.name[:70]}')

            to_deactivate.extend(rest)

        self.stdout.write(f'\nИтого к удалению в {label}: {len(to_deactivate)} товаров')

        if dry_run:
            return len(to_deactivate)

        pks = [p.pk for p in to_deactivate]
        updated = Product.objects.filter(pk__in=pks).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'Деактивировано {updated} дубликатов в {label} каталоге.'))
        return updated

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        do_retail = options['retail'] or options['all_catalogs']
        do_wholesale = not options['retail'] or options['all_catalogs']

        total = 0
        if do_wholesale:
            total += self._process_catalog('wholesale', dry_run)
        if do_retail:
            total += self._process_catalog('retail', dry_run)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY-RUN] Всего к удалению: {total}. Запустите без --dry-run.'
            ))
