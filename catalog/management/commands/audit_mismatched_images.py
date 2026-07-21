"""
Только отчёт (ничего не меняет в БД и файлах).

Ищет фото, у которых имя файла похоже на артикул, но этот код
не совпадает с артикулом / кросс-номером / кросс-номерами карточки.
Так находят редкие «залипшие» фото после смены артикула в 1С.

  python manage.py audit_mismatched_images
  python manage.py audit_mismatched_images --limit 50
"""
import os
import re

from django.core.management.base import BaseCommand

from catalog.models import ProductImage
from catalog.services import _bulk_image_basename_for_match, _cross_numbers_tokens, _oem_compact


def _looks_like_article_filename(stem: str) -> bool:
    t = (stem or '').strip()
    if len(t) < 4 or len(t) > 48:
        return False
    if re.search(r'[а-яА-ЯёЁ]', t):
        return False
    if not re.search(r'\d', t):
        return False
    return bool(re.fullmatch(r'[\dA-Za-z][\w\-]*[\dA-Za-z]|[\dA-Za-z]{4,}', t))


def _product_has_code(product, key: str) -> bool:
    k = (key or '').strip().lstrip('/')
    if not k or not product:
        return False
    kc = _oem_compact(k)
    for field in (product.supplier_article, product.article):
        val = (field or '').strip()
        if not val:
            continue
        if val.lower() == k.lower() or _oem_compact(val) == kc:
            return True
        if re.fullmatch(r'\d{4,14}', k) and (
            val.lower().startswith(k.lower() + '(')
            or val.lower().startswith(k.lower() + '/')
            or val.lower().startswith(k.lower() + '-')
            or val.lower().startswith(k.lower() + ' ')
        ):
            return True
        if '/' in val or '-' in val:
            head = re.split(r'[/\-]', val, maxsplit=1)[0].strip()
            if head.lower() == k.lower():
                return True
    for tok in _cross_numbers_tokens(product.cross_numbers or ''):
        if tok.strip().lower() == k.lower() or _oem_compact(tok) == kc:
            return True
    return False


class Command(BaseCommand):
    help = 'Отчёт: фото, имя файла которых не совпадает с кодами товара (без изменений)'

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
            stem = _bulk_image_basename_for_match(basename)
            if not stem:
                continue
            if stem.lower().endswith('_shared'):
                skipped_shared += 1
                continue
            if not _looks_like_article_filename(stem):
                continue
            if _product_has_code(product, stem):
                continue
            suspicious.append((img, product, stem, basename))

        self.stdout.write(f'Проверено изображений: {checked}')
        self.stdout.write(f'Пропущено shared-фото: {skipped_shared}')
        self.stdout.write(
            self.style.WARNING(
                f'Подозрительных (код файла ≠ коды карточки): {len(suspicious)}'
            )
        )

        for img, product, stem, basename in suspicious[:limit]:
            self.stdout.write(
                f'  img#{img.pk} file={basename!r} key={stem!r} → '
                f'product#{product.pk} [{product.catalog_type}] '
                f'art={product.supplier_article!r} cross={product.article!r} '
                f'name={(product.name or "")[:80]!r}'
            )
        if len(suspicious) > limit:
            self.stdout.write(f'  ... и ещё {len(suspicious) - limit}')

        self.stdout.write(
            self.style.NOTICE(
                '\nКоманда ничего не меняет. Чужие фото удаляйте вручную в админке '
                'и при необходимости перезаливайте файл с именем = артикул товара.'
            )
        )
