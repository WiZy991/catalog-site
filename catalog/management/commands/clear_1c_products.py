"""
Команда для удаления всех товаров из 1С перед новым обменом.
Удаляет только товары с external_id (из 1С), сохраняя товары, созданные вручную.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product, ProductImage
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Удаляет все товары из 1С (с external_id) перед новым обменом'

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
            # ВАЖНО: Используем транзакцию для безопасности
            with transaction.atomic():
                # Удаляем изображения товаров (CASCADE должно работать автоматически, но на всякий случай)
                deleted_images = 0
                for product in products_to_delete:
                    images_count = product.images.count()
                    if images_count > 0:
                        product.images.all().delete()
                        deleted_images += images_count
                
                # Удаляем товары
                deleted_count = products_to_delete.count()
                products_to_delete.delete()
                
                self.stdout.write(self.style.SUCCESS(f"✓ Удалено товаров: {deleted_count}"))
                if deleted_images > 0:
                    self.stdout.write(self.style.SUCCESS(f"✓ Удалено изображений: {deleted_images}"))
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
