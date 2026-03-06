"""
Синхронизирует поле description из розничных товаров в оптовые.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product


class Command(BaseCommand):
    help = 'Синхронизирует поле description из розничных товаров в оптовые'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет изменено, без фактического изменения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим все оптовые товары
        wholesale_products = Product.objects.filter(catalog_type='wholesale')
        
        updated_count = 0
        skipped_count = 0
        
        for wholesale_product in wholesale_products:
            # Ищем розничный аналог
            if not wholesale_product.external_id:
                skipped_count += 1
                continue
            
            retail_product = Product.objects.filter(
                external_id=wholesale_product.external_id,
                catalog_type='retail'
            ).first()
            
            if not retail_product:
                skipped_count += 1
                continue
            
            # Если у розничного товара есть description, копируем его в оптовый
            if retail_product.description and retail_product.description.strip():
                retail_description = retail_product.description.strip()
                # Обновляем только если оптовый товар не имеет description или имеет другое
                if not wholesale_product.description or wholesale_product.description.strip() != retail_description:
                    if dry_run:
                        self.stdout.write(
                            f'[DRY RUN] Будет обновлено описание у товара "{wholesale_product.name}" '
                            f'(ID: {wholesale_product.pk}) из розничного аналога: {retail_description[:50]}...'
                        )
                    else:
                        wholesale_product.description = retail_description
                        wholesale_product.save(update_fields=['description'])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Обновлено описание у товара "{wholesale_product.name}" (ID: {wholesale_product.pk})'
                            )
                        )
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Будет обновлено описаний: {updated_count}, '
                    f'пропущено: {skipped_count}'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Запустите команду без --dry-run для фактического обновления'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Готово! Обновлено описаний: {updated_count}, пропущено: {skipped_count}'
                )
            )
