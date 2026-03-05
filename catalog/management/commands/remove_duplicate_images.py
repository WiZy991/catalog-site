"""
Удаляет дубликаты изображений у товаров.
Дубликаты определяются по имени файла (без расширения и номера).
"""
from django.core.management.base import BaseCommand
from catalog.models import Product, ProductImage
import os
import re
from collections import defaultdict


class Command(BaseCommand):
    help = 'Удаляет дубликаты изображений у товаров'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим все товары с изображениями
        products = Product.objects.filter(images__isnull=False).distinct()
        
        total_deleted = 0
        products_processed = 0
        
        for product in products:
            images = product.images.all().order_by('id')
            
            if images.count() <= 1:
                continue
            
            products_processed += 1
            
            # Группируем изображения по базовому имени файла
            image_groups = defaultdict(list)
            
            for img in images:
                if not img.image:
                    continue
                
                # Получаем имя файла
                filename = os.path.basename(img.image.name)
                # Убираем расширение
                base_name = os.path.splitext(filename)[0]
                # Убираем номер в конце (_1, _2, -1 и т.д.)
                base_name = re.sub(r'[_-]?\d+$', '', base_name)
                # Приводим к нижнему регистру для сравнения
                base_name = base_name.lower()
                
                image_groups[base_name].append(img)
            
            # Удаляем дубликаты (оставляем первое изображение в группе)
            deleted_in_product = 0
            for base_name, group in image_groups.items():
                if len(group) > 1:
                    # Сортируем по ID, чтобы оставить самое старое
                    group_sorted = sorted(group, key=lambda x: x.id)
                    # Оставляем первое, удаляем остальные
                    to_delete = group_sorted[1:]
                    
                    for img in to_delete:
                        if dry_run:
                            self.stdout.write(
                                f'[DRY RUN] Будет удалено изображение "{img.image.name}" '
                                f'у товара "{product.name}" (ID: {product.pk}) - дубликат "{base_name}"'
                            )
                        else:
                            img.delete()
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Удалено изображение "{img.image.name}" у товара "{product.name}"'
                                )
                            )
                    
                    deleted_in_product += len(to_delete)
            
            if deleted_in_product > 0:
                total_deleted += deleted_in_product
        
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
