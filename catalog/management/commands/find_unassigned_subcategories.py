"""
Диагностика товаров, которые находятся в корневых категориях без подкатегории.

Примеры:
    python manage.py find_unassigned_subcategories
    python manage.py find_unassigned_subcategories --catalog-type retail
    python manage.py find_unassigned_subcategories --catalog-type wholesale
    python manage.py find_unassigned_subcategories --root "Двигатель и выхлопная система"
    python manage.py find_unassigned_subcategories --limit 200
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.models import Category, Product
from catalog.services import get_category_for_product


class Command(BaseCommand):
    help = "Показывает товары, которые остались в корневой категории (без подкатегории)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--catalog-type",
            type=str,
            choices=["retail", "wholesale", "both"],
            default="retail",
            help="Тип каталога для анализа (retail, wholesale, both).",
        )
        parser.add_argument(
            "--root",
            type=str,
            default="",
            help="Название корневой категории для фильтра (точное, без учета регистра).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Максимум строк в детальном выводе. 0 = без лимита (по умолчанию).",
        )
        parser.add_argument(
            "--all-statuses",
            action="store_true",
            help="Не ограничивать только видимыми товарами (is_active/quantity/availability).",
        )

    def handle(self, *args, **options):
        catalog_type = options["catalog_type"]
        root_name = (options.get("root") or "").strip()
        limit = max(0, int(options.get("limit") or 0))
        unlimited = limit == 0
        all_statuses = bool(options.get("all_statuses"))

        catalog_types = ["retail", "wholesale"] if catalog_type == "both" else [catalog_type]
        roots_qs = Category.objects.filter(parent__isnull=True, is_active=True)
        if root_name:
            roots_qs = roots_qs.filter(name__iexact=root_name)

        roots = list(roots_qs.order_by("name"))
        if not roots:
            self.stdout.write(self.style.WARNING("Корневые категории не найдены по фильтрам."))
            return

        self.stdout.write("=" * 90)
        self.stdout.write(self.style.SUCCESS("ПОИСК ТОВАРОВ БЕЗ ПОДКАТЕГОРИИ (сидят в root)"))
        self.stdout.write("=" * 90)
        self.stdout.write(f"Каталоги: {', '.join(catalog_types)}")
        self.stdout.write(f"Корней в выборке: {len(roots)}")
        self.stdout.write(f"Лимит детального вывода: {'без лимита' if unlimited else limit}")
        self.stdout.write(f"Режим по статусам: {'ВСЕ' if all_statuses else 'ТОЛЬКО ВИДИМЫЕ'}")

        total_root_products = 0
        total_lines_printed = 0
        total_recommended_child = 0

        for ct in catalog_types:
            self.stdout.write("")
            self.stdout.write("-" * 90)
            self.stdout.write(self.style.SUCCESS(f"Каталог: {ct.upper()}"))
            self.stdout.write("-" * 90)

            ct_total_root_products = 0
            ct_recommended_child = 0

            for root in roots:
                qs = Product.objects.filter(category=root, catalog_type=ct)
                if not all_statuses:
                    if ct == "retail":
                        qs = qs.filter(
                            is_active=True,
                            quantity__gt=0,
                        ).filter(Q(availability="in_stock") | Q(availability="order"))
                    else:
                        qs = qs.filter(
                            is_active=True,
                        ).filter(
                            Q(quantity__gt=0) | Q(wholesale_price__gt=0) | Q(availability__in=["in_stock", "order"])
                        )

                count_root = qs.count()
                if count_root == 0:
                    continue

                ct_total_root_products += count_root
                total_root_products += count_root

                self.stdout.write("")
                self.stdout.write(f"Root: {root.name} | товаров в root: {count_root}")

                if unlimited:
                    products_for_print = qs.order_by("id")
                else:
                    products_for_print = qs.order_by("id")[: max(0, limit - total_lines_printed)]

                for product in products_for_print:
                    new_category = get_category_for_product(product.name, use_db_subcategories=True)
                    suggestion = "-"
                    is_child = False
                    if new_category:
                        if new_category.parent_id:
                            suggestion = f"{new_category.parent.name} > {new_category.name}"
                            is_child = True
                        else:
                            suggestion = new_category.name
                    if is_child:
                        ct_recommended_child += 1
                        total_recommended_child += 1

                    self.stdout.write(
                        f"  id={product.id} | art={product.article or '-'} | "
                        f"name={str(product.name or '')[:90]} | suggest={suggestion}"
                    )
                    total_lines_printed += 1
                    if (not unlimited) and total_lines_printed >= limit:
                        break

                if (not unlimited) and total_lines_printed >= limit:
                    self.stdout.write(self.style.WARNING(f"\nДостигнут лимит вывода: {limit} строк."))
                    break

            self.stdout.write("")
            self.stdout.write(
                f"Итог {ct.upper()}: товаров в root={ct_total_root_products}, "
                f"из них классификатор уже предлагает child={ct_recommended_child}"
            )
            if (not unlimited) and total_lines_printed >= limit:
                break

        self.stdout.write("")
        self.stdout.write("=" * 90)
        self.stdout.write(
            self.style.SUCCESS(
                f"ВСЕГО найдено товаров в root: {total_root_products}; "
                f"из них с предложением child: {total_recommended_child}"
            )
        )
        self.stdout.write("=" * 90)
