"""
Команда для синхронизации товаров из оптового каталога в розничный.
Создает товары в розничном каталоге, если они есть только в оптовом.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Создает товары в розничном каталоге на основе товаров из оптового каталога'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет создано, без фактического создания',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("=" * 80)
        self.stdout.write("СИНХРОНИЗАЦИЯ ТОВАРОВ ИЗ ОПТОВОГО КАТАЛОГА В РОЗНИЧНЫЙ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ (dry-run) - изменения не будут применены"))
            self.stdout.write()
        
        # Находим товары в оптовом каталоге с остатками > 0
        wholesale_products = Product.objects.filter(
            catalog_type='wholesale',
            quantity__gt=0,
            is_active=True,
            external_id__isnull=False,
            external_id__gt=''
        )
        
        # Находим external_id товаров в розничном каталоге
        retail_external_ids = set(
            Product.objects.filter(
                catalog_type='retail',
                external_id__isnull=False,
                external_id__gt=''
            ).values_list('external_id', flat=True)
        )
        
        # Товары, которые есть в оптовом, но нет в розничном
        products_to_create = []
        for wholesale_product in wholesale_products:
            if wholesale_product.external_id not in retail_external_ids:
                products_to_create.append(wholesale_product)
        
        count = len(products_to_create)
        
        self.stdout.write(f"Найдено товаров в оптовом каталоге, которых нет в розничном: {count}")
        self.stdout.write()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Все товары из оптового каталога есть в розничном"))
            return
        
        # Показываем примеры
        self.stdout.write("Примеры товаров для создания в розничном каталоге (первые 10):")
        for i, product in enumerate(products_to_create[:10], 1):
            self.stdout.write(
                f"  {i}. {product.name[:50]} (артикул: {product.article}, "
                f"external_id: {product.external_id}, количество: {product.quantity})"
            )
        self.stdout.write()
        
        if not dry_run:
            created = 0
            for wholesale_product in products_to_create:
                # Создаем товар в розничном каталоге на основе оптового
                retail_product = Product(
                    external_id=wholesale_product.external_id,
                    article=wholesale_product.article or '',
                    name=wholesale_product.name or '',
                    brand=wholesale_product.brand or '',
                    category=wholesale_product.category,
                    description=wholesale_product.description or '',
                    short_description=wholesale_product.short_description or '',
                    applicability=wholesale_product.applicability or '',
                    cross_numbers=wholesale_product.cross_numbers or '',
                    characteristics=wholesale_product.characteristics or '',
                    farpost_url=wholesale_product.farpost_url or '',
                    condition=wholesale_product.condition or 'new',
                    price=wholesale_product.price or 0,
                    wholesale_price=wholesale_product.wholesale_price or 0,
                    quantity=wholesale_product.quantity,
                    availability=wholesale_product.availability,
                    catalog_type='retail',
                    is_active=True if (wholesale_product.quantity > 0 or wholesale_product.price > 0) else False
                )
                retail_product.save()
                created += 1
            
            self.stdout.write(self.style.SUCCESS(f"✓ Создано товаров в розничном каталоге: {created}"))
        else:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ - товары НЕ были созданы"))
            self.stdout.write("Запустите команду без --dry-run для фактического создания")
        
        self.stdout.write()
        self.stdout.write("=" * 80)
