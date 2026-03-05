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
            
            # Группируем изображения по комбинации: базовое имя + размер файла
            # Django добавляет случайные суффиксы типа _RuKm5tn, поэтому нужно извлекать базовое имя
            image_groups = defaultdict(list)
            
            for img in images:
                if not img.image:
                    continue
                
                try:
                    # Получаем имя файла
                    filename = os.path.basename(img.image.name)
                    # Убираем расширение
                    base_name = os.path.splitext(filename)[0]
                    
                    # Django добавляет случайные суффиксы типа _RuKm5tn (обычно 7-8 символов)
                    # Убираем их: ищем паттерн _XXXXXXX или _XXXXXXXX в конце
                    # Паттерн: подчеркивание + буквы/цифры (обычно 7-8 символов)
                    base_name = re.sub(r'_[A-Za-z0-9]{7,8}$', '', base_name)
                    
                    # Извлекаем артикул и номер фото из имени файла
                    # Формат файлов: АРТИКУЛ_НОМЕР или просто АРТИКУЛ
                    # Например: 43530-60042_1 -> артикул: 43530-60042, номер: 1
                    #           23300-78090 -> артикул: 23300-78090, номер: None
                    #           ME220745_1 -> артикул: ME220745, номер: 1
                    
                    # Сначала убираем случайный суффикс Django (если есть)
                    # Django добавляет суффиксы типа _RuKm5tn (7-8 символов)
                    base_name_clean = re.sub(r'_[A-Za-z0-9]{7,8}$', '', base_name)
                    
                    # Теперь извлекаем артикул и номер фото
                    # Паттерн: артикул может содержать буквы, цифры, дефисы
                    # Номер фото - это _1, _2, _3 и т.д. в конце (но не случайный суффикс Django)
                    match = re.match(r'^(.+?)(?:_(\d+))?$', base_name_clean)
                    if match:
                        article_part = match.group(1)  # Артикул (до _1, _2 и т.д.)
                        photo_number = match.group(2) if match.group(2) else None  # Номер фото (_1, _2)
                    else:
                        article_part = base_name_clean
                        photo_number = None
                    
                    # Получаем размер файла
                    file_size = 0
                    if hasattr(img.image, 'size'):
                        try:
                            file_size = img.image.size
                        except:
                            pass
                    
                    # Группируем по комбинации: артикул + номер фото + размер
                    # Это позволяет находить дубликаты даже если Django добавил разные суффиксы
                    # Например: 43530-60042_1_RuKm5tn.jpg и 43530-60042_1_J6zCbsD.jpg - это дубликаты
                    group_key = (article_part.lower(), photo_number, file_size)
                    image_groups[group_key].append(img)
                    
                except Exception as e:
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠ Ошибка при обработке изображения {img.id}: {e}'
                            )
                        )
                    continue
            
            # Удаляем дубликаты (группировка по артикулу + номер фото + размер)
            deleted_in_product = 0
            for (article_part, photo_number, file_size), group in image_groups.items():
                if len(group) > 1:
                    # Сортируем по ID, чтобы оставить самое старое
                    group_sorted = sorted(group, key=lambda x: x.id)
                    # Оставляем первое, удаляем остальные
                    to_delete = group_sorted[1:]
                    
                    for img in to_delete:
                        filename = os.path.basename(img.image.name) if img.image else 'N/A'
                        photo_info = f'"{article_part}"'
                        if photo_number:
                            photo_info += f' фото #{photo_number}'
                        if dry_run:
                            self.stdout.write(
                                f'[DRY RUN] Будет удалено изображение "{filename}" '
                                f'у товара "{product.name}" (ID: {product.pk}) - дубликат {photo_info} ({file_size} байт)'
                            )
                        else:
                            img.delete()
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Удалено изображение "{filename}" у товара "{product.name}" (дубликат {photo_info})'
                                )
                            )
                    
                    deleted_in_product += len(to_delete)
            
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
