"""
Удаляет записи ProductImage, у которых файл не существует на диске.
Использование: python manage.py fix_broken_images [--dry-run]
"""
from django.core.management.base import BaseCommand
from catalog.models import ProductImage


class Command(BaseCommand):
    help = 'Удаляет записи ProductImage с отсутствующими файлами на диске'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, не удалять',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        broken = []

        total = ProductImage.objects.count()
        self.stdout.write(f'Проверяем {total} записей ProductImage...')

        for pi in ProductImage.objects.select_related('product').iterator():
            try:
                if not pi.image or not pi.image.storage.exists(pi.image.name):
                    broken.append(pi)
            except Exception:
                broken.append(pi)

        self.stdout.write(f'Найдено битых записей: {len(broken)}')

        if not broken:
            self.stdout.write(self.style.SUCCESS('Всё в порядке, битых записей нет.'))
            return

        for pi in broken:
            product_info = f'Product #{pi.product_id}'
            if pi.product:
                product_info = f'{pi.product.article or pi.product.name} (id={pi.product_id})'
            self.stdout.write(f'  - ProductImage #{pi.pk}: {pi.image.name} -> {product_info}')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] Будет удалено {len(broken)} записей. '
                'Запустите без --dry-run для удаления.'
            ))
        else:
            pks = [pi.pk for pi in broken]
            deleted, _ = ProductImage.objects.filter(pk__in=pks).delete()
            self.stdout.write(self.style.SUCCESS(f'Удалено {deleted} битых записей ProductImage.'))
