"""
Находит и удаляет дубликаты wholesale-товаров (одинаковый артикул).
Оставляет товар с наиболее полными данными (по длине name + characteristics).
Использование:
  python manage.py remove_duplicate_wholesale --dry-run
  python manage.py remove_duplicate_wholesale
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from catalog.models import Product


class Command(BaseCommand):
    help = 'Удаляет дубликаты wholesale-товаров, оставляя наиболее полный'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать дубликаты, не удалять',
        )

    def _completeness(self, product):
        """Оценка полноты данных: чем больше — тем лучше."""
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

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        dupes = (
            Product.objects.filter(is_active=True, catalog_type='wholesale')
            .exclude(article='')
            .exclude(article__isnull=True)
            .values('article')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
            .order_by('-cnt')
        )

        total_articles = dupes.count()
        if total_articles == 0:
            self.stdout.write(self.style.SUCCESS('Дубликатов не найдено.'))
            return

        self.stdout.write(f'Найдено артикулов с дубликатами: {total_articles}')

        to_deactivate = []

        for dupe in dupes:
            article = dupe['article']
            products = list(
                Product.objects.filter(
                    article=article,
                    catalog_type='wholesale',
                    is_active=True,
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

        self.stdout.write(f'\nИтого к удалению: {len(to_deactivate)} товаров')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '[DRY-RUN] Запустите без --dry-run для удаления.'
            ))
            return

        pks = [p.pk for p in to_deactivate]
        updated = Product.objects.filter(pk__in=pks).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(
            f'Деактивировано {updated} дубликатов wholesale-товаров.'
        ))
