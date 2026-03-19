"""
Команда для удаления всех товаров из 1С перед новым обменом.
Удаляет только товары с external_id (из 1С), сохраняя товары, созданные вручную.
"""
import random
import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, close_old_connections, transaction

from catalog.models import Product, ProductImage


class Command(BaseCommand):
    help = 'Удаляет все товары из 1С (с external_id) перед новым обменом'

    def _run_with_sqlite_retry(self, fn, *, max_retries=8, delay=0.2, op_name="operation"):
        """
        SQLite может отдавать 'database is locked' если параллельно работает импорт/сайт/cron.
        Чтобы команда не падала, делаем retry с backoff и небольшим jitter.
        """
        for attempt in range(max_retries):
            try:
                return fn()
            except OperationalError as e:
                msg = str(e).lower()
                is_locked = 'database is locked' in msg or 'database table is locked' in msg
                if is_locked and attempt < max_retries - 1:
                    close_old_connections()
                    backoff = delay * (2 ** attempt)
                    jitter = random.uniform(0, delay)
                    self.stdout.write(self.style.WARNING(
                        f"SQLite locked during {op_name}, retry {attempt + 1}/{max_retries} in {backoff + jitter:.2f}s..."
                    ))
                    time.sleep(backoff + jitter)
                    continue
                raise

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )
        parser.add_argument(
            '--catalog-type',
            type=str,
            choices=['retail', 'wholesale', 'all'],
            default='all',
            help='Тип каталога для очистки (retail, wholesale, all)',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Подтвердить удаление без интерактивного ввода (для cron/CI)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_type = options['catalog_type']
        
        self.stdout.write("=" * 80)
        self.stdout.write("ОЧИСТКА ТОВАРОВ ИЗ 1С")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ (dry-run) - товары НЕ будут удалены"))
            self.stdout.write()
        else:
            self.stdout.write(self.style.ERROR("ВНИМАНИЕ: Будет удалено ВСЕ товары из 1С!"))
            self.stdout.write(self.style.ERROR("Убедитесь, что у вас есть резервная копия базы данных!"))
            self.stdout.write()
            self.stdout.write(self.style.WARNING("Подсказка: используйте --dry-run для проверки без удаления."))
            self.stdout.write(self.style.WARNING("Для неинтерактивного запуска добавьте --yes"))
            self.stdout.write()
            if not options.get('yes'):
                confirm = input("Введите 'yes' для подтверждения: ")
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.WARNING("Операция отменена"))
                    return
        
        # Фильтруем товары из 1С (с external_id)
        filters = {
            'external_id__isnull': False,
            'external_id__gt': ''
        }
        
        if catalog_type != 'all':
            filters['catalog_type'] = catalog_type
        
        products_to_delete = Product.objects.filter(**filters)
        
        # Подсчитываем статистику
        total_count = products_to_delete.count()
        retail_count = products_to_delete.filter(catalog_type='retail').count()
        wholesale_count = products_to_delete.filter(catalog_type='wholesale').count()
        
        self.stdout.write(f"Найдено товаров из 1С для удаления:")
        self.stdout.write(f"  - Всего: {total_count}")
        if catalog_type == 'all':
            self.stdout.write(f"  - Розничный каталог: {retail_count}")
            self.stdout.write(f"  - Оптовый каталог: {wholesale_count}")
        self.stdout.write()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("Нет товаров из 1С для удаления"))
            return
        
        # Показываем примеры товаров для удаления
        self.stdout.write("Примеры товаров для удаления (первые 10):")
        for i, product in enumerate(products_to_delete[:10], 1):
            self.stdout.write(
                f"  {i}. {product.name[:50]} (артикул: {product.article}, "
                f"external_id: {product.external_id[:50]}, каталог: {product.catalog_type})"
            )
        self.stdout.write()
        
        if not dry_run:
            # ВАЖНО:
            # - не держим одну длинную транзакцию на весь объём (SQLite легко ловит lock)
            # - удаляем батчами
            # - изображения удаляем bulk-ом, без N+1 по товарам
            batch_size = 200
            deleted_products_total = 0
            deleted_images_total = 0

            while True:
                # Берём следующий батч id (детерминированно)
                batch_ids = list(products_to_delete.order_by('id').values_list('id', flat=True)[:batch_size])
                if not batch_ids:
                    break

                def _delete_batch():
                    nonlocal deleted_products_total, deleted_images_total
                    with transaction.atomic():
                        # Сначала удаляем изображения для батча
                        images_qs = ProductImage.objects.filter(product_id__in=batch_ids)
                        deleted_images_total += images_qs.count()
                        images_qs.delete()

                        # Потом товары батча
                        deleted_products_total += Product.objects.filter(id__in=batch_ids).count()
                        Product.objects.filter(id__in=batch_ids).delete()

                self._run_with_sqlite_retry(_delete_batch, op_name=f"delete batch (size={len(batch_ids)})")

            self.stdout.write(self.style.SUCCESS(f"✓ Удалено товаров: {deleted_products_total}"))
            if deleted_images_total > 0:
                self.stdout.write(self.style.SUCCESS(f"✓ Удалено изображений: {deleted_images_total}"))
        else:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ - товары НЕ были удалены"))
            self.stdout.write("Запустите команду без --dry-run для фактического удаления")
        
        self.stdout.write()
        self.stdout.write("=" * 80)
        self.stdout.write()
        self.stdout.write("Следующие шаги:")
        self.stdout.write("1. Выполните обмен с 1С (загрузите import.xml и offers.xml)")
        self.stdout.write("2. Проверьте количество товаров:")
        self.stdout.write("   python manage.py find_missing_from_1c")
        self.stdout.write()
