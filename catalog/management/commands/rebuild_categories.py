"""
Management command для пересчёта дерева категорий MPTT.
Используйте после изменения порядка категорий в админке.
"""
from django.core.management.base import BaseCommand
from catalog.models import Category


class Command(BaseCommand):
    help = 'Пересчитывает дерево категорий MPTT после изменения порядка сортировки'

    def handle(self, *args, **options):
        self.stdout.write('Пересчёт дерева категорий...')
        
        # Пересчитываем дерево MPTT
        Category.objects.rebuild()
        
        # Выводим статистику
        total = Category.objects.count()
        root_count = Category.objects.filter(parent=None).count()
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Дерево категорий пересчитано успешно!\n'
            f'   Всего категорий: {total}\n'
            f'   Корневых категорий: {root_count}'
        ))
        
        # Выводим порядок корневых категорий (по алфавиту)
        self.stdout.write('\nПорядок корневых категорий (А-Я):')
        for i, cat in enumerate(Category.objects.filter(parent=None).order_by('name'), 1):
            self.stdout.write(f'   {i}. {cat.name}')
