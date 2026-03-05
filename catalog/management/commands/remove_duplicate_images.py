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
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Показать подробную информацию о процессе',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options.get('verbose', False)
        
        # Находим все товары с изображениями
        products = Product.objects.filter(images__isnull=False).distinct()
        
        total_deleted = 0
        products_processed = 0
        
        for product in products:
            images = product.images.all().order_by('id')
            
            if images.count() <= 1:
                continue
            
            products_processed += 1
            
            # Группируем изображения по базовому имени файла И по размеру файла
            image_groups_by_name = defaultdict(list)
            image_groups_by_size = defaultdict(list)
            
            for img in images:
                if not img.image:
                    continue
                
                try:
                    # Получаем имя файла
                    filename = os.path.basename(img.image.name)
                    # Убираем расширение
                    base_name = os.path.splitext(filename)[0]
                    # Убираем номер в конце (_1, _2, -1 и т.д.)
                    base_name = re.sub(r'[_-]?\d+$', '', base_name)
                    # Приводим к нижнему регистру для сравнения
                    base_name = base_name.lower()
                    
                    image_groups_by_name[base_name].append(img)
                    
                    # Также группируем по размеру файла (если файл существует)
                    if img.image and hasattr(img.image, 'size'):
                        try:
                            file_size = img.image.size
                            image_groups_by_size[file_size].append(img)
                        except:
                            pass
                except Exception as e:
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠ Ошибка при обработке изображения {img.id}: {e}'
                            )
                        )
                    continue
            
            # Удаляем дубликаты по имени файла
            deleted_in_product = 0
            for base_name, group in image_groups_by_name.items():
                if len(group) > 1:
                    # Сортируем по ID, чтобы оставить самое старое
                    group_sorted = sorted(group, key=lambda x: x.id)
                    # Оставляем первое, удаляем остальные
                    to_delete = group_sorted[1:]
                    
                    for img in to_delete:
                        if dry_run:
                            self.stdout.write(
                                f'[DRY RUN] Будет удалено изображение "{img.image.name}" '
                                f'у товара "{product.name}" (ID: {product.pk}) - дубликат по имени "{base_name}"'
                            )
                        else:
                            img.delete()
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Удалено изображение "{img.image.name}" у товара "{product.name}"'
                                )
                            )
                    
                    deleted_in_product += len(to_delete)
            
            # Также проверяем дубликаты по размеру файла (если имя не совпало, но размер одинаковый)
            for file_size, group in image_groups_by_size.items():
                if len(group) > 1:
                    # Проверяем, не были ли уже удалены эти изображения
                    group = [img for img in group if img.id]  # Фильтруем уже удаленные
                    if len(group) > 1:
                        # Сортируем по ID, оставляем первое
                        group_sorted = sorted(group, key=lambda x: x.id)
                        to_delete = group_sorted[1:]
                        
                        for img in to_delete:
                            # Проверяем, не было ли это уже удалено по имени
                            if img.id:  # Если изображение еще существует
                                if dry_run:
                                    self.stdout.write(
                                        f'[DRY RUN] Будет удалено изображение "{img.image.name}" '
                                        f'у товара "{product.name}" (ID: {product.pk}) - дубликат по размеру ({file_size} байт)'
                                    )
                                else:
                                    img.delete()
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'✓ Удалено изображение "{img.image.name}" у товара "{product.name}" (дубликат по размеру)'
                                        )
                                    )
                                deleted_in_product += 1
            
            if deleted_in_product > 0:
                total_deleted += deleted_in_product
            elif verbose:
                # Показываем информацию о товаре, если дубликатов не найдено
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
