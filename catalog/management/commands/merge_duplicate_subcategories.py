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

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        stats = merge_duplicate_subcategories(dry_run=dry_run)

        mode = 'DRY-RUN' if dry_run else 'APPLY'
        self.stdout.write(self.style.SUCCESS(f'[{mode}] merge_duplicate_subcategories'))
        self.stdout.write(f"Групп дублей: {stats.get('groups', 0)}")
        self.stdout.write(f"Слитых категорий: {stats.get('merged_categories', 0)}")
        self.stdout.write(f"Перенесено товаров: {stats.get('moved_products', 0)}")
        self.stdout.write(f"Перенесено дочерних категорий: {stats.get('moved_children', 0)}")
        self.stdout.write(f"Деактивировано дублей: {stats.get('deactivated', 0)}")
