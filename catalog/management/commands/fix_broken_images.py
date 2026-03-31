"""
Находит и исправляет записи ProductImage с проблемными путями файлов
(содержащими пробелы, слэши и другие спецсимволы в имени файла).
Использование:
  python manage.py fix_broken_images --dry-run    # показать проблемные записи
  python manage.py fix_broken_images              # исправить (перенести файлы)
"""
import os
import re
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import get_valid_filename
from catalog.models import ProductImage


class Command(BaseCommand):
    help = 'Находит и исправляет ProductImage с проблемными путями файлов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать проблемы, не исправлять',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        total = ProductImage.objects.count()
        self.stdout.write(f'Проверяем {total} записей ProductImage...')

        missing = []
        bad_path = []

        for pi in ProductImage.objects.select_related('product').iterator():
            name = pi.image.name if pi.image else ''

            if not name:
                missing.append(pi)
                continue

            if not pi.image.storage.exists(name):
                missing.append(pi)
                continue

            basename = os.path.basename(name)
            dirname = os.path.dirname(name)

            has_nested_slash = dirname.count('/') > 0 and dirname.count('/') > dirname.replace('products/', '', 1).count('/') + (1 if dirname.startswith('products/') else 0)
            safe_basename = get_valid_filename(basename)
            expected_dir = 'products'

            parts = name.split('/')
            if len(parts) > 2:
                bad_path.append(pi)
            elif basename != safe_basename:
                bad_path.append(pi)
            elif ' ' in name:
                bad_path.append(pi)

        self.stdout.write(f'Записей с отсутствующими файлами: {len(missing)}')
        self.stdout.write(f'Записей с проблемными путями: {len(bad_path)}')

        if missing:
            self.stdout.write(self.style.WARNING('\n--- Отсутствующие файлы ---'))
            for pi in missing[:20]:
                product_info = f'{pi.product.article or pi.product.name} (id={pi.product_id})' if pi.product else f'Product #{pi.product_id}'
                self.stdout.write(f'  ProductImage #{pi.pk}: "{pi.image.name}" -> {product_info}')
            if len(missing) > 20:
                self.stdout.write(f'  ... и ещё {len(missing) - 20}')

        if bad_path:
            self.stdout.write(self.style.WARNING('\n--- Проблемные пути ---'))
            for pi in bad_path[:20]:
                product_info = f'{pi.product.article or pi.product.name} (id={pi.product_id})' if pi.product else f'Product #{pi.product_id}'
                self.stdout.write(f'  ProductImage #{pi.pk}: "{pi.image.name}" -> {product_info}')
            if len(bad_path) > 20:
                self.stdout.write(f'  ... и ещё {len(bad_path) - 20}')

        if not missing and not bad_path:
            self.stdout.write(self.style.SUCCESS('Проблем не найдено.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY-RUN] Проблемных записей: {len(missing) + len(bad_path)}. '
                'Запустите без --dry-run для исправления.'
            ))
            return

        fixed = 0
        deleted = 0

        for pi in bad_path:
            try:
                old_name = pi.image.name
                old_content = pi.image.read()
                pi.image.close()

                safe_name = get_valid_filename(os.path.basename(old_name))
                new_name = f'products/{safe_name}'

                pi.image.save(safe_name, ContentFile(old_content), save=True)
                fixed += 1

                try:
                    storage = pi.image.storage
                    if storage.exists(old_name) and old_name != pi.image.name:
                        storage.delete(old_name)
                except Exception:
                    pass

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Ошибка при исправлении #{pi.pk}: {e}'))

        if missing:
            pks = [pi.pk for pi in missing]
            del_count, _ = ProductImage.objects.filter(pk__in=pks).delete()
            deleted = del_count

        self.stdout.write(self.style.SUCCESS(
            f'\nИсправлено путей: {fixed}, удалено битых записей: {deleted}'
        ))
