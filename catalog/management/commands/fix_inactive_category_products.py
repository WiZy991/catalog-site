"""
Команда для исправления товаров, которые находятся в неактивных категориях.
Перемещает товары из неактивных категорий в активные родительские категории.
"""

from django.core.management.base import BaseCommand
from catalog.models import Product, Category


class Command(BaseCommand):
    help = 'Перемещает товары из неактивных категорий в активные родительские категории'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет сделано, без реальных изменений',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим все товары в неактивных категориях
        products_in_inactive_categories = Product.objects.filter(
            category__is_active=False
        ).select_related('category')
        
        total_count = products_in_inactive_categories.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('✓ Все товары находятся в активных категориях'))
            return
        
        self.stdout.write(f'Найдено товаров в неактивных категориях: {total_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] Режим проверки - изменения не будут применены\n'))
        
        moved_count = 0
        skipped_count = 0
        
        for product in products_in_inactive_categories:
            old_category = product.category
            if not old_category:
                skipped_count += 1
                continue
            
            # Ищем активную родительскую категорию (поднимаемся по дереву)
            current_cat = old_category
            active_parent = None
            
            while current_cat:
                if current_cat.parent and current_cat.parent.is_active:
                    active_parent = current_cat.parent
                    break
                current_cat = current_cat.parent
            
            if not active_parent:
                # Если нет активной родительской, используем первую активную корневую
                active_parent = Category.objects.filter(parent=None, is_active=True).first()
            
            if active_parent:
                if dry_run:
                    self.stdout.write(
                        f'[DRY RUN] Товар "{product.name[:50]}" (ID: {product.id}) '
                        f'будет перемещен из "{old_category.name}" в "{active_parent.name}"'
                    )
                else:
                    product.category = active_parent
                    product.save(update_fields=['category'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Товар "{product.name[:50]}" перемещен из "{old_category.name}" в "{active_parent.name}"'
                        )
                    )
                moved_count += 1
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ Товар "{product.name[:50]}" (ID: {product.id}) '
                        f'в неактивной категории "{old_category.name}" - нет активной родительской категории'
                    )
                )
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'Всего товаров в неактивных категориях: {total_count}')
        self.stdout.write(f'Перемещено в активные категории: {moved_count}')
        self.stdout.write(f'Пропущено (нет активной родительской): {skipped_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] Запустите без --dry-run для применения изменений'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Готово!'))
