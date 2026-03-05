"""
Удаляет дубликаты изображений у оптовых товаров, которые имеют розничные аналоги с изображениями.
Оптовые товары должны использовать изображения розничных аналогов через методы get_main_image() и get_all_images().
"""
from django.core.management.base import BaseCommand
from catalog.models import Product, ProductImage


class Command(BaseCommand):
    help = 'Удаляет дубликаты изображений у оптовых товаров, если есть розничный аналог с изображениями'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим все оптовые товары
        wholesale_products = Product.objects.filter(catalog_type='wholesale')
        
        deleted_count = 0
        checked_count = 0
        
        for wholesale_product in wholesale_products:
            # Проверяем, есть ли у оптового товара изображения
            if not wholesale_product.images.exists():
                continue
            
            checked_count += 1
            
            # Ищем розничный аналог
            if not wholesale_product.external_id:
                continue
            
            retail_product = Product.objects.filter(
                external_id=wholesale_product.external_id,
                catalog_type='retail'
            ).first()
            
            # Если есть розничный аналог с изображениями, удаляем изображения у оптового
            if retail_product and retail_product.images.exists():
                images_count = wholesale_product.images.count()
                
                if dry_run:
                    self.stdout.write(
                        f'[DRY RUN] Будет удалено {images_count} изображений у оптового товара '
                        f'"{wholesale_product.name}" (ID: {wholesale_product.pk}) - есть розничный аналог с изображениями'
                    )
                else:
                    wholesale_product.images.all().delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Удалено {images_count} изображений у оптового товара '
                            f'"{wholesale_product.name}" (ID: {wholesale_product.pk})'
                        )
                    )
                
                deleted_count += images_count
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Всего будет удалено изображений: {deleted_count} '
                    f'у {checked_count} оптовых товаров'
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
                    f'\n✓ Готово! Удалено изображений: {deleted_count} у {checked_count} оптовых товаров'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    'Оптовые товары теперь используют изображения розничных аналогов'
                )
            )
