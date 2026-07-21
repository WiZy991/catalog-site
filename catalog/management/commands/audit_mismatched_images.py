"""
Только отчёт (ничего не меняет в БД и файлах).

Ищет редкие «залипшие» фото: имя файла = код другого товара,
а на текущей карточке этого кода нет (ни в артикуле, ни в названии).

Не ругается на нормальные случаи:
  - Django-суффикс в имени (23731-35U10_1_AbCdEfGh.jpg)
  - OEM в названии, но не в поле артикула (331008.jpg → «…331008…» в name)

  python manage.py audit_mismatched_images
  python manage.py audit_mismatched_images --limit 50
"""
import os
import re

from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.models import Product, ProductImage
from catalog.services import _bulk_image_basename_for_match, _cross_numbers_tokens, _oem_compact


def _extract_file_article_key(basename: str) -> str:
    """Код из сохранённого имени: снять суффикс Django, затем _1 / (2) как при заливке."""
    stem = os.path.splitext(os.path.basename(basename or ''))[0].strip()
    stem = re.sub(r'_[A-Za-z0-9]{7,8}$', '', stem)
    return _bulk_image_basename_for_match(stem)


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
            if head.lower() == k.lower() or _oem_compact(head) == kc:
                return True
    for tok in _cross_numbers_tokens(product.cross_numbers or ''):
        if tok.strip().lower() == k.lower() or _oem_compact(tok) == kc:
            return True
    return False


def _code_in_product_name(product, key: str) -> bool:
    """Код есть в названии как отдельный фрагмент (OEM в длинном name)."""
    k = (key or '').strip()
    if len(k) < 4:
        return False
    name = (product.name or '')
    if not name:
        return False
    pattern = re.compile(r'(?<![\w\-/])' + re.escape(k) + r'(?![\w\-/])', re.IGNORECASE)
    return bool(pattern.search(name))


def _find_other_product_with_code(key: str, exclude_pk: int):
    """Другая карточка, у которой key — артикул или кросс-номер."""
    k = (key or '').strip().lstrip('/')
    if not k:
        return None
    kc = _oem_compact(k)
    base = Product.objects.exclude(pk=exclude_pk).filter(is_active=True)

    hit = base.filter(Q(supplier_article__iexact=k) | Q(article__iexact=k)).first()
    if hit:
        return hit

    norm_article = kc.lower()
    for p in base.exclude(Q(article='') & Q(supplier_article=''))[:2000]:
        for field in (p.supplier_article, p.article):
            val = (field or '').strip()
            if val and _oem_compact(val) == norm_article:
                return p
        for tok in _cross_numbers_tokens(p.cross_numbers or ''):
            if tok.strip().lower() == k.lower() or _oem_compact(tok) == kc:
                return p
    return None


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
            if not _looks_like_article_filename(file_key):
                continue

            if _product_has_code(product, file_key):
                skipped_ok += 1
                continue
            if _code_in_product_name(product, file_key):
                skipped_ok += 1
                continue

            other = _find_other_product_with_code(file_key, product.pk)
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
