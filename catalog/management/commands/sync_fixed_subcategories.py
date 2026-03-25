from django.core.management.base import BaseCommand

from catalog.services import sync_all_subcategories_from_keywords


class Command(BaseCommand):
    help = (
        "Синхронизирует фиксированные подкатегории для корневых категорий: "
        "добавляет их в keywords и создает/обновляет дочерние категории."
    )

    def handle(self, *args, **options):
        totals = sync_all_subcategories_from_keywords(root_only=True)
        self.stdout.write(
            self.style.SUCCESS(
                "Готово. "
                f"Создано: {totals.get('created', 0)}, "
                f"обновлено: {totals.get('updated', 0)}, "
                f"деактивировано: {totals.get('deactivated', 0)}"
            )
        )
