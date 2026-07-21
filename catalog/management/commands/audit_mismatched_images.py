"""
Только отчёт (ничего не меняет в БД и файлах).

Ищет редкие «залипшие» фото: имя файла = код другого товара,
а на текущей карточке этого кода нет (ни в артикуле, ни в названии).

  python manage.py audit_mismatched_images
  python manage.py audit_mismatched_images --limit 50
"""
import os
import re

from django.core.management.base import BaseCommand

from catalog.models import ProductImage
from catalog.services import (
    _bulk_image_basename_for_match,
    _find_product_with_field_code,
    _filename_looks_like_part_number,
    _product_fields_have_code,
    _product_name_has_code_token,
)


def _extract_file_article_key(basename: str) -> str:
    stem = os.path.splitext(os.path.basename(basename or ''))[0].strip()
    stem = re.sub(r'_[A-Za-z0-9]{7,8}$', '', stem)
    return _bulk_image_basename_for_match(stem)


class Command(BaseCommand):
    help = (
        'Отчёт: фото, код в имени файла принадлежит другому товару '
        '(без изменений в БД)'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Сколько подозрительных строк показать (по умолчанию 100)',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        suspicious = []
        skipped_shared = 0
        skipped_ok = 0
        checked = 0

        qs = (
            ProductImage.objects.select_related('product')
            .exclude(image='')
            .order_by('id')
        )
        for img in qs.iterator(chunk_size=500):
            checked += 1
            product = img.product
            if not product:
                continue
            basename = os.path.basename(img.image.name or '')
            file_key = _extract_file_article_key(basename)
            if not file_key:
                continue
            if file_key.lower().endswith('_shared'):
                skipped_shared += 1
                continue
            if not _filename_looks_like_part_number(file_key):
                continue

            if _product_fields_have_code(product, file_key):
                skipped_ok += 1
                continue
            if _product_name_has_code_token(product, file_key):
                skipped_ok += 1
                continue

            other = _find_product_with_field_code(file_key, exclude_pk=product.pk)
            if not other:
                continue

            suspicious.append((img, product, file_key, basename, other))

        self.stdout.write(f'Проверено изображений: {checked}')
        self.stdout.write(f'Совпало с кодами/названием карточки: {skipped_ok}')
        self.stdout.write(f'Пропущено shared-фото: {skipped_shared}')
        self.stdout.write(
            self.style.WARNING(
                f'Подозрительных (код файла = другой товар): {len(suspicious)}'
            )
        )

        for img, product, file_key, basename, other in suspicious[:limit]:
            self.stdout.write(
                f'  img#{img.pk} file={basename!r} key={file_key!r}\n'
                f'    на карточке: #{product.pk} [{product.catalog_type}] '
                f'art={product.supplier_article!r} cross={product.article!r}\n'
                f'    вероятно для: #{other.pk} [{other.catalog_type}] '
                f'art={other.supplier_article!r} cross={other.article!r} '
                f'name={(other.name or "")[:60]!r}'
            )
        if len(suspicious) > limit:
            self.stdout.write(f'  ... и ещё {len(suspicious) - limit}')

        if not suspicious:
            self.stdout.write(self.style.SUCCESS('Подозрительных фото не найдено.'))

        self.stdout.write(
            self.style.NOTICE(
                '\nКоманда ничего не меняет. Если строка попала в список — '
                'проверьте вручную и при необходимости перенесите/удалите фото.'
            )
        )
