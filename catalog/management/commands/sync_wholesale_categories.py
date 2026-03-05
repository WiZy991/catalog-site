from django.core.management.base import BaseCommand
from django.db import transaction
from catalog.models import Product


class Command(BaseCommand):
    help = 'Синхронизирует категории оптовых товаров с категориями розничных аналогов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, что будет изменено, без реального сохранения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('РЕЖИМ ПРОСМОТРА (--dry-run): изменения НЕ сохраняются'))

        # Берём все оптовые товары
        wholesale_products = Product.objects.filter(
            catalog_type='wholesale'
        ).select_related('category')

        total = wholesale_products.count()
        self.stdout.write(f'Всего оптовых товаров: {total}')

        updated = 0
        not_found = 0
        already_correct = 0

        to_update = []

        for product in wholesale_products.iterator(chunk_size=500):
            # Ищем розничный аналог по external_id (приоритет), затем по артикулу
            retail = None
            if product.external_id and product.external_id.strip():
                retail = Product.objects.filter(
                    external_id=product.external_id.strip(),
                    catalog_type='retail'
                ).select_related('category').first()

            if not retail and product.article and product.article.strip():
                retail = Product.objects.filter(
                    article=product.article.strip(),
                    catalog_type='retail'
                ).select_related('category').first()

            if not retail:
                not_found += 1
                continue

            if retail.category_id == product.category_id:
                already_correct += 1
                continue

            # Категория отличается — нужно синхронизировать
            old_category = str(product.category) if product.category else 'None'
            new_category = str(retail.category) if retail.category else 'None'

            self.stdout.write(
                f'  [{product.article or product.external_id}] '
                f'{old_category!r} → {new_category!r}'
            )

            if not dry_run:
                product.category = retail.category
                to_update.append(product)

            updated += 1

        # Сохраняем в БД одной транзакцией
        if not dry_run and to_update:
            with transaction.atomic():
                for product in to_update:
                    product.save(update_fields=['category'])

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Будет обновлено:   {updated} (dry-run, не сохранено)'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Обновлено:         {updated}'))
        self.stdout.write(f'Уже верные:        {already_correct}')
        self.stdout.write(f'Без розн. аналога: {not_found}')
