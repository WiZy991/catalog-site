"""
Management команда для перераспределения товаров по категориям и подкатегориям.

Использование:
    python manage.py redistribute_categories --catalog-type retail
    python manage.py redistribute_categories --catalog-type wholesale
    python manage.py redistribute_categories --catalog-type both
    
Перераспределяет все товары по категориям на основе их названий,
используя функцию get_category_for_product.
"""
import logging
from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from catalog.models import Product, Category
from catalog.services import get_category_for_product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Перераспределяет товары по категориям и подкатегориям на основе их названий'

    def add_arguments(self, parser):
        parser.add_argument(
            '--catalog-type',
            type=str,
            choices=['retail', 'wholesale', 'both'],
            default='both',
            help='Тип каталога для обработки (retail, wholesale, both)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено без сохранения в БД',
        )

    def handle(self, *args, **options):
        catalog_type = options['catalog_type']
        dry_run = options['dry_run']
        
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('ПЕРЕРАСПРЕДЕЛЕНИЕ ТОВАРОВ ПО КАТЕГОРИЯМ'))
        self.stdout.write('=' * 80)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('РЕЖИМ ПРОСМОТРА (dry-run) - изменения не будут сохранены'))
        
        # Определяем какие каталоги обрабатывать
        catalog_types = []
        if catalog_type == 'both':
            catalog_types = ['retail', 'wholesale']
        else:
            catalog_types = [catalog_type]
        
        total_processed = 0
        total_updated = 0
        total_errors = 0
        
        stats_by_category = {}
        
        for ct in catalog_types:
            self.stdout.write('')
            self.stdout.write('-' * 80)
            self.stdout.write(f'Обработка каталога: {ct.upper()}')
            self.stdout.write('-' * 80)
            
            # Получаем все активные товары этого каталога
            products = Product.objects.filter(
                catalog_type=ct,
                is_active=True
            ).select_related('category')
            
            total_count = products.count()
            self.stdout.write(f'Найдено товаров: {total_count}')
            
            if total_count == 0:
                self.stdout.write(self.style.WARNING(f'  Нет товаров для обработки в каталоге {ct}'))
                continue
            
            updated_count = 0
            error_count = 0
            unchanged_count = 0
            
            # Обрабатываем товары батчами
            batch_size = 100
            for i in range(0, total_count, batch_size):
                batch = products[i:i+batch_size]
                
                for product in batch:
                    try:
                        # Определяем категорию на основе названия товара
                        # Используем исходное название (name), так как в нём могут быть ключевые слова
                        category = get_category_for_product(product.name)
                        
                        if not category:
                            self.stdout.write(self.style.ERROR(f'  ⚠ Товар {product.id} ({product.article}): не удалось определить категорию'))
                            error_count += 1
                            continue
                        
                        # Проверяем, изменилась ли категория
                        old_category = product.category
                        if old_category != category:
                            if not dry_run:
                                product.category = category
                                product.save(update_fields=['category'])
                            
                            updated_count += 1
                            
                            # Статистика по категориям
                            cat_name = category.name
                            if category.parent:
                                cat_name = f"{category.parent.name} > {category.name}"
                            
                            if cat_name not in stats_by_category:
                                stats_by_category[cat_name] = {'retail': 0, 'wholesale': 0}
                            stats_by_category[cat_name][ct] = stats_by_category[cat_name][ct] + 1
                            
                            if updated_count <= 10:  # Показываем первые 10 изменений
                                old_cat_name = old_category.name if old_category else 'НЕТ'
                                if old_category and old_category.parent:
                                    old_cat_name = f"{old_category.parent.name} > {old_cat_name}"
                                self.stdout.write(f'  ✓ Товар {product.id} ({product.article[:20]}): {old_cat_name} -> {cat_name}')
                        else:
                            unchanged_count += 1
                        
                        total_processed += 1
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ✗ Ошибка при обработке товара {product.id}: {str(e)}'))
                        logger.exception(f'Ошибка при обработке товара {product.id}')
                        error_count += 1
                        total_errors += 1
                
                # Прогресс
                processed = min(i + batch_size, total_count)
                self.stdout.write(f'  Обработано: {processed}/{total_count} ({processed*100//total_count}%)')
            
            total_updated += updated_count
            
            self.stdout.write('')
            self.stdout.write(f'Статистика для каталога {ct.upper()}:')
            self.stdout.write(f'  Всего обработано: {total_count}')
            self.stdout.write(f'  Обновлено: {updated_count}')
            self.stdout.write(f'  Без изменений: {unchanged_count}')
            self.stdout.write(f'  Ошибок: {error_count}')
        
        # Итоговая статистика
        self.stdout.write('')
        self.stdout.write('=' * 80)
        self.stdout.write('ИТОГОВАЯ СТАТИСТИКА')
        self.stdout.write('=' * 80)
        self.stdout.write(f'Всего обработано товаров: {total_processed}')
        self.stdout.write(f'Обновлено категорий: {total_updated}')
        self.stdout.write(f'Ошибок: {total_errors}')
        
        # Статистика по категориям
        if stats_by_category:
            self.stdout.write('')
            self.stdout.write('Распределение по категориям:')
            self.stdout.write('-' * 80)
            
            # Сортируем по общему количеству товаров
            sorted_cats = sorted(
                stats_by_category.items(),
                key=lambda x: x[1]['retail'] + x[1]['wholesale'],
                reverse=True
            )
            
            for cat_name, counts in sorted_cats[:20]:  # Показываем топ-20
                total_in_cat = counts['retail'] + counts['wholesale']
                retail_str = f"retail: {counts['retail']}" if counts['retail'] > 0 else ""
                wholesale_str = f"wholesale: {counts['wholesale']}" if counts['wholesale'] > 0 else ""
                parts = [p for p in [retail_str, wholesale_str] if p]
                self.stdout.write(f'  {cat_name}: {total_in_cat} ({", ".join(parts)})')
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('РЕЖИМ ПРОСМОТРА - изменения не были сохранены'))
            self.stdout.write('Запустите без --dry-run для применения изменений')
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ Перераспределение завершено!'))
