"""
Показывает все изображения товаров для диагностики дубликатов.
"""
from django.core.management.base import BaseCommand
from django.db import models
from catalog.models import Product, ProductImage
import os


class Command(BaseCommand):
    help = 'Показывает все изображения товаров для диагностики'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product-id',
            type=int,
            help='Показать изображения только для конкретного товара (ID)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Ограничить количество товаров (по умолчанию 20)',
        )

    def handle(self, *args, **options):
        product_id = options.get('product_id')
        limit = options.get('limit', 20)
        
        if product_id:
            products = Product.objects.filter(pk=product_id)
        else:
            # Находим товары с несколькими изображениями
            products = Product.objects.annotate(
                image_count=models.Count('images')
            ).filter(image_count__gt=1).order_by('-image_count')[:limit]
        
        if not products.exists():
            self.stdout.write(self.style.WARNING('Товары с несколькими изображениями не найдены'))
            return
        
        for product in products:
            images = product.images.all().order_by('id')
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{"="*80}\n'
                    f'Товар: "{product.name}" (ID: {product.pk}, Артикул: {product.article})\n'
                    f'Количество изображений: {images.count()}\n'
                    f'{"="*80}'
                )
            )
            
            for idx, img in enumerate(images, 1):
                filename = os.path.basename(img.image.name) if img.image else 'Нет файла'
                file_size = ''
                if img.image:
                    try:
                        if hasattr(img.image, 'size'):
                            file_size = f', размер: {img.image.size} байт'
                    except:
                        pass
                
                self.stdout.write(
                    f'  {idx}. ID: {img.id}, Файл: "{filename}"{file_size}, '
                    f'Главное: {img.is_main}, Порядок: {img.order}'
                )
