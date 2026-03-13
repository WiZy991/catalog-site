"""
Команда для поиска товаров из 1С, которые должны быть на сайте, но отсутствуют.
Сравнивает товары из 1С (с external_id) с товарами на сайте.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product
from django.db.models import Q


class Command(BaseCommand):
    help = 'Находит товары из 1С, которые должны быть на сайте, но отсутствуют'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ПОИСК ПРОПАВШИХ ТОВАРОВ ИЗ 1С")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        # Ожидаемое количество товаров из 1С с остатками
        expected_count = 2504
        
        # Товары из 1С (с external_id) в розничном каталоге
        # Которые ДОЛЖНЫ показываться на сайте: quantity > 0 И price > 0
        retail_from_1c = Product.objects.filter(
            catalog_type='retail',
            external_id__isnull=False,
            external_id__gt='',
            quantity__gt=0,
            price__gt=0,
            is_active=True,
            category__isnull=False,
            category__is_active=True
        )
        
        retail_count = retail_from_1c.count()
        
        self.stdout.write(f"Ожидается товаров из 1С с остатками: {expected_count}")
        self.stdout.write(f"Товаров из 1С на сайте (quantity > 0 И price > 0): {retail_count}")
        self.stdout.write(f"РАЗНИЦА: {expected_count - retail_count}")
        self.stdout.write()
        
        # Проверяем товары из 1С в розничном каталоге с остатками, но с проблемами
        retail_with_issues = Product.objects.filter(
            catalog_type='retail',
            external_id__isnull=False,
            external_id__gt='',
            quantity__gt=0
        )
        
        # С ценой = 0
        retail_price_zero = retail_with_issues.filter(price=0).count()
        if retail_price_zero > 0:
            self.stdout.write(f"⚠ Товаров из 1С с остатками > 0, но с ценой = 0: {retail_price_zero}")
            examples = retail_with_issues.filter(price=0)[:5]
            for p in examples:
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, external_id: {p.external_id}, количество: {p.quantity}, цена: {p.price})")
            self.stdout.write()
        
        # Неактивные
        retail_inactive = retail_with_issues.filter(is_active=False).count()
        if retail_inactive > 0:
            self.stdout.write(f"⚠ Товаров из 1С с остатками > 0, но неактивных: {retail_inactive}")
            examples = retail_with_issues.filter(is_active=False)[:5]
            for p in examples:
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, external_id: {p.external_id}, количество: {p.quantity}, цена: {p.price})")
            self.stdout.write()
        
        # Без категории
        retail_no_category = retail_with_issues.filter(category__isnull=True).count()
        if retail_no_category > 0:
            self.stdout.write(f"⚠ Товаров из 1С с остатками > 0, но без категории: {retail_no_category}")
            examples = retail_with_issues.filter(category__isnull=True)[:5]
            for p in examples:
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, external_id: {p.external_id}, количество: {p.quantity}, цена: {p.price})")
            self.stdout.write()
        
        # В неактивных категориях
        retail_in_inactive_category = retail_with_issues.filter(category__is_active=False).count()
        if retail_in_inactive_category > 0:
            self.stdout.write(f"⚠ Товаров из 1С с остатками > 0, но в неактивных категориях: {retail_in_inactive_category}")
            examples = retail_with_issues.filter(category__is_active=False)[:5]
            for p in examples:
                cat_name = p.category.name if p.category else 'НЕТ'
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, категория: {cat_name}, количество: {p.quantity}, цена: {p.price})")
            self.stdout.write()
        
        # Проверяем товары в оптовом каталоге, которых нет в розничном
        wholesale_from_1c = Product.objects.filter(
            catalog_type='wholesale',
            external_id__isnull=False,
            external_id__gt='',
            quantity__gt=0,
            wholesale_price__gt=0,
            is_active=True
        )
        
        wholesale_external_ids = set(wholesale_from_1c.values_list('external_id', flat=True))
        retail_external_ids = set(
            Product.objects.filter(
                catalog_type='retail',
                external_id__isnull=False,
                external_id__gt=''
            ).values_list('external_id', flat=True)
        )
        
        missing_in_retail = wholesale_external_ids - retail_external_ids
        if missing_in_retail:
            self.stdout.write(f"⚠ Товаров из 1С есть в ОПТОВОМ каталоге, но НЕТ в РОЗНИЧНОМ: {len(missing_in_retail)}")
            examples = wholesale_from_1c.filter(external_id__in=list(missing_in_retail)[:5])
            for p in examples:
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, external_id: {p.external_id}, количество: {p.quantity}, оптовая цена: {p.wholesale_price})")
            self.stdout.write()
        
        # Итоговая статистика
        self.stdout.write("=" * 80)
        self.stdout.write("ИТОГО")
        self.stdout.write("=" * 80)
        self.stdout.write()
        self.stdout.write(f"Товаров из 1С на сайте (quantity > 0 И price > 0): {retail_count}")
        self.stdout.write(f"Ожидается: {expected_count}")
        self.stdout.write(f"Не хватает: {expected_count - retail_count}")
        self.stdout.write()
        
        # Возможные причины пропажи
        total_missing_reasons = retail_price_zero + retail_inactive + retail_no_category + retail_in_inactive_category + len(missing_in_retail)
        self.stdout.write("Возможные причины пропажи товаров:")
        if retail_price_zero > 0:
            self.stdout.write(f"  - С ценой = 0: {retail_price_zero}")
        if retail_inactive > 0:
            self.stdout.write(f"  - Неактивных: {retail_inactive}")
        if retail_no_category > 0:
            self.stdout.write(f"  - Без категории: {retail_no_category}")
        if retail_in_inactive_category > 0:
            self.stdout.write(f"  - В неактивных категориях: {retail_in_inactive_category}")
        if missing_in_retail:
            self.stdout.write(f"  - Только в оптовом каталоге: {len(missing_in_retail)}")
        
        remaining = expected_count - retail_count - total_missing_reasons
        if remaining > 0:
            self.stdout.write(f"  - Не импортированы из 1С (нет в базе): {remaining}")
        
        self.stdout.write()
        self.stdout.write("=" * 80)
