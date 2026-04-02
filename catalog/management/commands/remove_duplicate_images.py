"""
Удаляет дубликаты изображений у товаров.

По умолчанию — по имени файла + размер (старая логика).
С флагом --by-content — по хешу содержимого файла (одинаковые байты,
в т.ч. после массовой загрузки с разными суффиксами в имени).
"""
import hashlib
import os
import re
from collections import defaultdict

from django.core.management.base import BaseCommand

from catalog.models import Product, ProductImage


def _image_content_hash(img):
    if not img.image:
        return None
    try:
        h = hashlib.md5()
        with img.image.open('rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Удаляет дубликаты изображений у товаров'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Показать подробную информацию о процессе',
        )
        parser.add_argument(
            '--by-content',
            action='store_true',
            help='Считать дубликатами файлы с одинаковым содержимым (MD5), '
                 'а не только по имени. Подходит для 2–3 одинаковых фото на карточке.',
        )

    def _ensure_one_main(self, product, dry_run):
        imgs = list(product.images.all().order_by('order', 'id'))
        if not imgs:
            return
        if any(i.is_main for i in imgs):
            return
        keeper = imgs[0]
        if dry_run:
            self.stdout.write(
                f'  [DRY RUN] У товара ID={product.pk} назначить главное фото ID={keeper.pk}'
            )
        else:
            keeper.is_main = True
            keeper.save(update_fields=['is_main'])

    def _handle_by_content(self, dry_run, verbose):
        products = Product.objects.filter(images__isnull=False).distinct()
        total_deleted = 0
        products_affected = 0

        for product in products.iterator(chunk_size=100):
            images = list(product.images.all().order_by('id'))
            if len(images) <= 1:
                continue

            by_hash = defaultdict(list)
            for img in images:
                digest = _image_content_hash(img)
                if digest is None:
                    by_hash[f'__error_{img.pk}__'].append(img)
                    continue
                by_hash[digest].append(img)

            deleted_here = 0
            for digest, group in by_hash.items():
                if digest.startswith('__error_') or len(group) <= 1:
                    continue
                group_sorted = sorted(
                    group,
                    key=lambda x: (-int(x.is_main), x.order, x.id),
                )
                keeper = group_sorted[0]
                for img in group_sorted[1:]:
                    fn = os.path.basename(img.image.name) if img.image else 'N/A'
                    if dry_run:
                        self.stdout.write(
                            f'[DRY RUN] Товар ID={product.pk} «{product.name[:50]}…»: '
                            f'удалить дубликат ID={img.pk} ({fn}), оставить ID={keeper.pk}'
                        )
                    else:
                        img.delete()
                        if verbose:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Товар ID={product.pk}: удалён дубликат ID={img.pk} ({fn})'
                                )
                            )
                    deleted_here += 1

            if deleted_here:
                total_deleted += deleted_here
                products_affected += 1
                if not dry_run:
                    self._ensure_one_main(product, dry_run=False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Будет удалено изображений: {total_deleted} '
                    f'у {products_affected} товаров (--by-content)'
                )
            )
            self.stdout.write(
                self.style.WARNING('Запустите без --dry-run для удаления.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Готово (--by-content). Удалено дубликатов: {total_deleted}, '
                    f'затронуто товаров: {products_affected}'
                )
            )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options.get('verbose', False)

        if options.get('by_content'):
            return self._handle_by_content(dry_run, verbose)

        # --- прежняя логика: имя файла + размер ---
        products = Product.objects.filter(images__isnull=False).distinct()

        total_deleted = 0
        products_processed = 0

        for product in products:
            images = product.images.all().order_by('id')

            if images.count() <= 1:
                continue

            products_processed += 1

            image_groups = defaultdict(list)

            for img in images:
                if not img.image:
                    continue

                try:
                    filename = os.path.basename(img.image.name)
                    base_name = os.path.splitext(filename)[0]

                    base_name = re.sub(r'_[A-Za-z0-9]{7,8}$', '', base_name)

                    base_name_clean = re.sub(r'_[A-Za-z0-9]{7,8}$', '', base_name)

                    match = re.match(r'^(.+?)(?:_(\d+))?$', base_name_clean)
                    if match:
                        article_part = match.group(1)
                        photo_number = match.group(2) if match.group(2) else None
                    else:
                        article_part = base_name_clean
                        photo_number = None

                    file_size = 0
                    if hasattr(img.image, 'size'):
                        try:
                            file_size = img.image.size
                        except Exception:
                            pass

                    group_key = (article_part.lower(), photo_number, file_size)
                    image_groups[group_key].append(img)

                except Exception as e:
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠ Ошибка при обработке изображения {img.id}: {e}'
                            )
                        )
                    continue

            deleted_in_product = 0
            for (article_part, photo_number, file_size), group in image_groups.items():
                if len(group) > 1:
                    group_sorted = sorted(group, key=lambda x: x.id)
                    to_delete = group_sorted[1:]

                    for img in to_delete:
                        filename = os.path.basename(img.image.name) if img.image else 'N/A'
                        photo_info = f'"{article_part}"'
                        if photo_number:
                            photo_info += f' фото #{photo_number}'
                        if dry_run:
                            self.stdout.write(
                                f'[DRY RUN] Будет удалено изображение "{filename}" '
                                f'у товара "{product.name}" (ID: {product.pk}) - дубликат {photo_info} ({file_size} байт)'
                            )
                        else:
                            img.delete()
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Удалено изображение "{filename}" у товара "{product.name}" (дубликат {photo_info})'
                                )
                            )

                    deleted_in_product += len(to_delete)

            if deleted_in_product > 0:
                total_deleted += deleted_in_product
                if not dry_run:
                    self._ensure_one_main(product, dry_run=False)
            elif verbose:
                self.stdout.write(
                    f'Товар "{product.name}" (ID: {product.pk}): {images.count()} изображений, дубликатов не найдено'
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Всего будет удалено изображений: {total_deleted} '
                    f'у {products_processed} товаров'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Запустите команду без --dry-run для фактического удаления'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Готово! Удалено изображений: {total_deleted} у {products_processed} товаров'
                )
            )
