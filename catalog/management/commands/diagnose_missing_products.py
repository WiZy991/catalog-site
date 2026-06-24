"""
Команда для диагностики пропавших товаров.
Сравнивает витрину с offers.xml (если указан файл) или показывает сводку по БД.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.models import Product


class Command(BaseCommand):
    help = 'Диагностика пропавших товаров'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='',
            help='Путь к offers.xml для точной сверки (рекомендуется)',
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('ДИАГНОСТИКА ПРОПАВШИХ ТОВАРОВ')
        self.stdout.write('=' * 80)
        self.stdout.write()

        offers_file = (options.get('file') or '').strip()
        if offers_file:
            if not os.path.isabs(offers_file):
                offers_file = os.path.join(settings.BASE_DIR, offers_file)
            if not os.path.exists(offers_file):
                self.stdout.write(self.style.ERROR(f'Файл не найден: {offers_file}'))
                return
            self.stdout.write(
                'Для точной сверки с 1С используйте:\n'
                f'  python manage.py reconcile_offers_site --file {offers_file}\n'
                f'  python manage.py reconcile_offers_site --file {offers_file} --apply\n'
            )
            self.stdout.write()
            from django.core.management import call_command
            call_command('reconcile_offers_site', file=offers_file)
            return

        retail_visible = Product.objects.filter(
            catalog_type='retail',
            is_active=True,
            quantity__gt=0,
        ).count()

        retail_hidden_with_stock = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=False,
        ).count()

        self.stdout.write('Сводка по базе (без файла offers — ожидаемое число из 1С неизвестно):')
        self.stdout.write(f'  - На витрине (retail, active, qty>0): {retail_visible}')
        self.stdout.write(f'  - Скрытые с остатком (retail, inactive, qty>0): {retail_hidden_with_stock}')
        self.stdout.write()
        self.stdout.write(
            'Метрика «скрытые с остатком» включает устаревшие карточки, которых уже нет в текущем offers.xml.'
        )
        self.stdout.write(
            'Для поиска реального разрыва с 1С укажите файл обмена:'
        )
        self.stdout.write('  python manage.py diagnose_missing_products --file xml_offers.txt')
        self.stdout.write('  python manage.py reconcile_offers_site --file xml_offers.txt --apply')
        self.stdout.write()

        if retail_hidden_with_stock > 0:
            self.stdout.write(self.style.WARNING(
                f'Примеры скрытых с остатком (первые 10 из {retail_hidden_with_stock}):'
            ))
            examples = Product.objects.filter(
                catalog_type='retail',
                quantity__gt=0,
                is_active=False,
            )[:10]
            for p in examples:
                self.stdout.write(
                    f'  * id={p.pk} article={p.article} qty={p.quantity} '
                    f'ext={p.external_id or "-"} | {p.name[:55]}'
                )

        self.stdout.write()
        self.stdout.write('=' * 80)
