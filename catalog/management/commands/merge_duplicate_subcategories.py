from django.core.management.base import BaseCommand

from catalog.services import merge_duplicate_subcategories


class Command(BaseCommand):
    help = 'Сливает дубли подкатегорий под одним родителем с переносом товаров.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать статистику без изменений в БД.',
        )
        parser.add_argument(
            '--delete-empty',
            action='store_true',
            help='Удалять пустые дубли (без товаров и дочерних категорий) после слияния.',
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        delete_empty = bool(options.get('delete_empty'))
        stats = merge_duplicate_subcategories(
            dry_run=dry_run,
            delete_empty_duplicates=delete_empty,
        )

        mode = 'DRY-RUN' if dry_run else 'APPLY'
        self.stdout.write(self.style.SUCCESS(f'[{mode}] merge_duplicate_subcategories'))
        self.stdout.write(f"Групп дублей: {stats.get('groups', 0)}")
        self.stdout.write(f"Слитых категорий: {stats.get('merged_categories', 0)}")
        self.stdout.write(f"Перенесено товаров: {stats.get('moved_products', 0)}")
        self.stdout.write(f"Перенесено дочерних категорий: {stats.get('moved_children', 0)}")
        self.stdout.write(f"Деактивировано дублей: {stats.get('deactivated', 0)}")
        self.stdout.write(f"Удалено пустых дублей: {stats.get('deleted', 0)}")