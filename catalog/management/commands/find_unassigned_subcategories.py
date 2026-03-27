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
        parser.add_argument(
            "--show-inactive-category-products",
            action="store_true",
            help="Показать товары, которые лежат в неактивных подкатегориях выбранных корней.",
        )
        parser.add_argument(
            "--audit-category-page-counts",
            action="store_true",
            help="Аудит расхождения: 'Найдено' vs сумма по активным прямым подкатегориям.",
        )

    def handle(self, *args, **options):
        catalog_type = options["catalog_type"]
        root_name = (options.get("root") or "").strip()
        limit = max(0, int(options.get("limit") or 0))
        unlimited = limit == 0
        all_statuses = bool(options.get("all_statuses"))
        show_inactive_category_products = bool(options.get("show_inactive_category_products"))
        audit_category_page_counts = bool(options.get("audit_category_page_counts"))

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

        def _visible_qs(catalog: str):
            qs_base = Product.objects.filter(catalog_type=catalog)
            if all_statuses:
                return qs_base
            if catalog == "retail":
                return qs_base.filter(
                    is_active=True,
                    quantity__gt=0,
                ).filter(Q(availability="in_stock") | Q(availability="order"))
            return qs_base.filter(
                is_active=True,
            ).filter(Q(quantity__gt=0) | Q(wholesale_price__gt=0) | Q(availability__in=["in_stock", "order"]))

        total_root_products = 0
        total_lines_printed = 0
        total_recommended_child = 0
        total_inactive_category_products = 0

        for ct in catalog_types:
            self.stdout.write("")
            self.stdout.write("-" * 90)
            self.stdout.write(self.style.SUCCESS(f"Каталог: {ct.upper()}"))
            self.stdout.write("-" * 90)

            ct_total_root_products = 0
            ct_recommended_child = 0
            ct_inactive_category_products = 0
            visible_qs = _visible_qs(ct)

            for root in roots:
                qs = visible_qs.filter(category=root)

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

            if show_inactive_category_products:
                self.stdout.write("")
                self.stdout.write(f"Проверка товаров в НЕАКТИВНЫХ подкатегориях ({ct.upper()})...")
                for root in roots:
                    inactive_descendants = root.get_descendants(include_self=False).filter(is_active=False)
                    if not inactive_descendants.exists():
                        continue
                    qs_inactive_cat = visible_qs.filter(
                        category__in=inactive_descendants,
                    )

                    inactive_count = qs_inactive_cat.count()
                    if inactive_count == 0:
                        continue

                    ct_inactive_category_products += inactive_count
                    total_inactive_category_products += inactive_count
                    self.stdout.write(
                        f"  Root: {root.name} | товаров в неактивных подкатегориях: {inactive_count}"
                    )

                    if unlimited:
                        products_for_print = qs_inactive_cat.select_related("category").order_by("id")
                    else:
                        products_for_print = qs_inactive_cat.select_related("category").order_by("id")[
                            : max(0, limit - total_lines_printed)
                        ]

                    for product in products_for_print:
                        self.stdout.write(
                            f"    id={product.id} | art={product.article or '-'} | "
                            f"cat={product.category.name if product.category else '-'} | "
                            f"name={str(product.name or '')[:90]}"
                        )
                        total_lines_printed += 1
                        if (not unlimited) and total_lines_printed >= limit:
                            break

                    if (not unlimited) and total_lines_printed >= limit:
                        self.stdout.write(self.style.WARNING(f"\nДостигнут лимит вывода: {limit} строк."))
                        break

                self.stdout.write(
                    f"Итог по неактивным подкатегориям {ct.upper()}: {ct_inactive_category_products}"
                )

            if audit_category_page_counts:
                self.stdout.write("")
                self.stdout.write(f"Аудит счетчиков страницы категории ({ct.upper()})...")
                for root in roots:
                    descendants = root.get_descendants(include_self=True)
                    has_active_direct = root.children.filter(is_active=True).exists()
                    if has_active_direct:
                        descendants = descendants.exclude(id=root.id)

                    found_qs = visible_qs.filter(category__in=descendants)
                    found_ids = set(found_qs.values_list("id", flat=True))
                    found_count = len(found_ids)

                    active_children = list(root.children.filter(is_active=True).order_by("name"))
                    children_total = 0
                    children_ids_union = set()
                    for child in active_children:
                        branch_ids = set(
                            found_qs.filter(category__in=child.get_descendants(include_self=True)).values_list("id", flat=True)
                        )
                        if branch_ids:
                            children_total += len(branch_ids)
                            children_ids_union.update(branch_ids)

                    diff_only_found = found_ids - children_ids_union
                    diff_only_children = children_ids_union - found_ids
                    self.stdout.write(
                        f"  Root={root.name} | found={found_count} | sum_children={children_total} | "
                        f"only_found={len(diff_only_found)} | only_children={len(diff_only_children)}"
                    )

                    # Печатаем проблемные товары: попали в found, но не попали в сумму активных direct-children.
                    if diff_only_found:
                        extra_qs = Product.objects.filter(id__in=diff_only_found).select_related("category").order_by("id")
                        if not unlimited:
                            extra_qs = extra_qs[: max(0, limit - total_lines_printed)]
                        for product in extra_qs:
                            self.stdout.write(
                                f"    [ONLY_FOUND] id={product.id} | cat={product.category.name if product.category else '-'} | "
                                f"art={product.article or '-'} | name={str(product.name or '')[:90]}"
                            )
                            total_lines_printed += 1
                            if (not unlimited) and total_lines_printed >= limit:
                                break
                    if (not unlimited) and total_lines_printed >= limit:
                        self.stdout.write(self.style.WARNING(f"\nДостигнут лимит вывода: {limit} строк."))
                        break
            if (not unlimited) and total_lines_printed >= limit:
                break

        self.stdout.write("")
        self.stdout.write("=" * 90)
        self.stdout.write(
            self.style.SUCCESS(
                f"ВСЕГО найдено товаров в root: {total_root_products}; "
                f"из них с предложением child: {total_recommended_child}; "
                f"товаров в неактивных подкатегориях: {total_inactive_category_products}"
            )
        )
        self.stdout.write("=" * 90)
