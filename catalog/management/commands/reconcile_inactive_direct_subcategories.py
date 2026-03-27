"""
Проверяет прямые неактивные подкатегории корней, в чьих ветках есть товары.
Опционально активирует такие direct-child категории.

Примеры:
    python manage.py reconcile_inactive_direct_subcategories
    python manage.py reconcile_inactive_direct_subcategories --root "Двигатель и выхлопная система"
    python manage.py reconcile_inactive_direct_subcategories --catalog-type retail --apply
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.models import Category, Product


class Command(BaseCommand):
    help = "Диагностика/исправление прямых неактивных подкатегорий с товарами в ветке."

    def add_arguments(self, parser):
        parser.add_argument(
            "--catalog-type",
            type=str,
            choices=["retail", "wholesale", "both"],
            default="retail",
            help="Тип каталога для проверки (retail, wholesale, both).",
        )
        parser.add_argument(
            "--root",
            type=str,
            default="",
            help="Название корневой категории (точное, регистронезависимо).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Применить изменения (по умолчанию только диагностика).",
        )

    def _visible_products_qs(self, catalog_type: str):
        qs = Product.objects.filter(catalog_type=catalog_type, is_active=True)
        if catalog_type == "retail":
            return qs.filter(quantity__gt=0).filter(Q(availability="in_stock") | Q(availability="order"))
        return qs.filter(Q(quantity__gt=0) | Q(wholesale_price__gt=0) | Q(availability__in=["in_stock", "order"]))

    def handle(self, *args, **options):
        root_name = (options.get("root") or "").strip()
        apply_changes = bool(options.get("apply"))
        ct_arg = options.get("catalog_type") or "retail"
        catalog_types = ["retail", "wholesale"] if ct_arg == "both" else [ct_arg]

        roots_qs = Category.objects.filter(parent__isnull=True)
        if root_name:
            roots_qs = roots_qs.filter(name__iexact=root_name)
        roots = list(roots_qs.order_by("name"))
        if not roots:
            self.stdout.write(self.style.WARNING("Корневые категории не найдены."))
            return

        self.stdout.write("=" * 90)
        self.stdout.write(
            self.style.SUCCESS(
                f"ПРОВЕРКА НЕАКТИВНЫХ ПРЯМЫХ ПОДКАТЕГОРИЙ | mode={'APPLY' if apply_changes else 'DRY-RUN'}"
            )
        )
        self.stdout.write("=" * 90)

        total_problematic = 0
        total_activated = 0

        for ct in catalog_types:
            self.stdout.write(f"\nКаталог: {ct.upper()}")
            visible_qs = self._visible_products_qs(ct)

            ct_problematic = 0
            ct_activated = 0

            for root in roots:
                direct_children = root.children.all().order_by("name")
                for child in direct_children:
                    if child.is_active:
                        continue
                    branch = child.get_descendants(include_self=True)
                    products_count = visible_qs.filter(category__in=branch).count()
                    if products_count <= 0:
                        continue

                    ct_problematic += 1
                    total_problematic += 1
                    self.stdout.write(
                        f"  root={root.name} | inactive_child={child.name} | товаров в ветке={products_count}"
                    )

                    if apply_changes:
                        child.is_active = True
                        child.save(update_fields=["is_active", "updated_at"])
                        ct_activated += 1
                        total_activated += 1
                        self.stdout.write("    -> activated")

            self.stdout.write(
                f"Итог {ct.upper()}: проблемных веток={ct_problematic}, "
                f"активировано={ct_activated}"
            )

        self.stdout.write("\n" + "=" * 90)
        self.stdout.write(
            self.style.SUCCESS(
                f"ИТОГО: проблемных веток={total_problematic}, активировано={total_activated}"
            )
        )
        self.stdout.write("=" * 90)
