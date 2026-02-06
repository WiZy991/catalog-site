from django.core.management.base import BaseCommand
from catalog.models import Category, Product


class Command(BaseCommand):
    help = 'Удаляет пустые категории (без товаров)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет удалено, но не удалять',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Удалить ВСЕ категории (даже с товарами)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_all = options['all']
        
        if delete_all:
            # Удаляем ВСЕ категории
            count = Category.objects.count()
            if dry_run:
                self.stdout.write(f'Будет удалено ВСЕ категории: {count}')
            else:
                Category.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Удалено ВСЕ категории: {count}'))
            return
        
        # Находим пустые категории (без товаров и без дочерних категорий с товарами)
        empty_categories = []
        
        for category in Category.objects.all():
            # Считаем товары в этой категории и всех её потомках
            descendants = category.get_descendants(include_self=True)
            product_count = Product.objects.filter(category__in=descendants).count()
            
            if product_count == 0:
                empty_categories.append(category)
        
        if not empty_categories:
            self.stdout.write(self.style.SUCCESS('Пустых категорий не найдено!'))
            return
        
        if dry_run:
            self.stdout.write(f'Найдено пустых категорий: {len(empty_categories)}')
            for cat in empty_categories:
                self.stdout.write(f'  - {cat.name} (ID: {cat.id})')
        else:
            # Удаляем начиная с листьев (чтобы избежать проблем с родительскими связями)
            deleted_count = 0
            for category in sorted(empty_categories, key=lambda c: -c.level):
                cat_name = category.name
                category.delete()
                deleted_count += 1
                self.stdout.write(f'Удалена: {cat_name}')
            
            self.stdout.write(self.style.SUCCESS(f'\nВсего удалено категорий: {deleted_count}'))
