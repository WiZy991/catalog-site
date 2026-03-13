"""
Команда для диагностики пропавших товаров.
Сравнивает количество товаров с остатками в 1С и на сайте.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product, Category
from django.db.models import Q


class Command(BaseCommand):
    help = 'Диагностика пропавших товаров'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ДИАГНОСТИКА ПРОПАВШИХ ТОВАРОВ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        # Ожидаемое количество товаров с остатками из 1С
        expected_count = 2504
        
        # Товары с остатками > 0
        products_with_stock = Product.objects.filter(quantity__gt=0)
        total_with_stock = products_with_stock.count()
        
        # Активные товары с остатками > 0
        active_with_stock = Product.objects.filter(
            quantity__gt=0,
            is_active=True
        )
        active_count = active_with_stock.count()
        
        # Товары с остатками > 0, но неактивные
        inactive_with_stock = Product.objects.filter(
            quantity__gt=0,
            is_active=False
        )
        inactive_count = inactive_with_stock.count()
        
        # Товары с остатками > 0 в розничном каталоге
        retail_with_stock = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0
        )
        retail_total = retail_with_stock.count()
        retail_active = retail_with_stock.filter(is_active=True).count()
        
        # Товары с остатками > 0 в оптовом каталоге
        wholesale_with_stock = Product.objects.filter(
            catalog_type='wholesale',
            quantity__gt=0
        )
        wholesale_total = wholesale_with_stock.count()
        wholesale_active = wholesale_with_stock.filter(is_active=True).count()
        
        self.stdout.write(f"Ожидается товаров с остатками из 1С: {expected_count}")
        self.stdout.write()
        self.stdout.write(f"В базе данных:")
        self.stdout.write(f"  - Всего товаров с остатками > 0: {total_with_stock}")
        self.stdout.write(f"  - Активных с остатками > 0: {active_count}")
        self.stdout.write(f"  - Неактивных с остатками > 0: {inactive_count}")
        self.stdout.write()
        self.stdout.write(f"Розничный каталог:")
        self.stdout.write(f"  - Всего с остатками > 0: {retail_total}")
        self.stdout.write(f"  - Активных с остатками > 0: {retail_active}")
        self.stdout.write()
        self.stdout.write(f"Оптовый каталог:")
        self.stdout.write(f"  - Всего с остатками > 0: {wholesale_total}")
        self.stdout.write(f"  - Активных с остатками > 0: {wholesale_active}")
        self.stdout.write()
        
        # Разница
        difference = expected_count - retail_active
        self.stdout.write(f"РАЗНИЦА: {expected_count} (ожидается) - {retail_active} (активных в розничном) = {difference}")
        self.stdout.write()
        
        # Инициализируем переменные для проверки категорий
        no_category = 0
        in_inactive_category = 0
        
        # Товары с остатками > 0, но неактивные (должны быть активны)
        if inactive_count > 0:
            self.stdout.write(self.style.WARNING(f"⚠ Найдено {inactive_count} неактивных товаров с остатками > 0:"))
            self.stdout.write()
            
            # Без категории
            no_category = inactive_with_stock.filter(category__isnull=True).count()
            if no_category > 0:
                self.stdout.write(f"  - Без категории: {no_category}")
                examples = inactive_with_stock.filter(category__isnull=True)[:5]
                for p in examples:
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity})")
                self.stdout.write()
            
            # В неактивных категориях
            in_inactive_category = inactive_with_stock.filter(category__is_active=False).count()
            if in_inactive_category > 0:
                self.stdout.write(f"  - В неактивных категориях: {in_inactive_category}")
                examples = inactive_with_stock.filter(category__is_active=False)[:5]
                for p in examples:
                    cat_name = p.category.name if p.category else 'НЕТ'
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, категория: {cat_name}, количество: {p.quantity})")
                self.stdout.write()
            
            # С ценой = 0
            with_zero_price = inactive_with_stock.filter(
                Q(price=0) & Q(wholesale_price=0)
            ).count()
            if with_zero_price > 0:
                self.stdout.write(f"  - С ценой = 0: {with_zero_price}")
                examples = inactive_with_stock.filter(
                    Q(price=0) & Q(wholesale_price=0)
                )[:5]
                for p in examples:
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, цена: {p.price}, оптовая: {p.wholesale_price})")
                self.stdout.write()
            
            # Остальные (с ценой > 0, в активных категориях)
            others = inactive_with_stock.exclude(
                category__isnull=True
            ).exclude(
                category__is_active=False
            ).filter(
                Q(price__gt=0) | Q(wholesale_price__gt=0)
            ).count()
            if others > 0:
                self.stdout.write(f"  - С ценой > 0, в активных категориях: {others}")
                examples = inactive_with_stock.exclude(
                    category__isnull=True
                ).exclude(
                    category__is_active=False
                ).filter(
                    Q(price__gt=0) | Q(wholesale_price__gt=0)
                )[:5]
                for p in examples:
                    self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, цена: {p.price})")
                self.stdout.write()
        
        # Проверяем товары в розничном каталоге с остатками, но не показывающиеся на сайте
        retail_with_stock_all = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=True
        )
        
        # Товары без категории
        retail_no_category = retail_with_stock_all.filter(category__isnull=True).count()
        if retail_no_category > 0:
            self.stdout.write(f"⚠ В розничном каталоге товаров с остатками > 0 БЕЗ КАТЕГОРИИ: {retail_no_category}")
            examples = retail_with_stock_all.filter(category__isnull=True)[:5]
            for p in examples:
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity})")
            self.stdout.write()
        
        # Товары в неактивных категориях
        retail_in_inactive_category = retail_with_stock_all.filter(category__is_active=False).count()
        if retail_in_inactive_category > 0:
            self.stdout.write(f"⚠ В розничном каталоге товаров с остатками > 0 В НЕАКТИВНЫХ КАТЕГОРИЯХ: {retail_in_inactive_category}")
            examples = retail_with_stock_all.filter(category__is_active=False)[:5]
            for p in examples:
                cat_name = p.category.name if p.category else 'НЕТ'
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, категория: {cat_name}, количество: {p.quantity})")
            self.stdout.write()
        
        # Товары с availability='out_of_stock' (должны быть 'in_stock' или 'order')
        retail_out_of_stock = retail_with_stock_all.filter(availability='out_of_stock').count()
        if retail_out_of_stock > 0:
            self.stdout.write(f"⚠ В розничном каталоге товаров с остатками > 0 но availability='out_of_stock': {retail_out_of_stock}")
            examples = retail_with_stock_all.filter(availability='out_of_stock')[:5]
            for p in examples:
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, количество: {p.quantity}, availability: {p.availability})")
            self.stdout.write()
        
        # Товары без external_id (не были импортированы из 1С)
        without_external_id = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=True,
            external_id__isnull=True
        ).count()
        if without_external_id > 0:
            self.stdout.write(f"⚠ В розничном каталоге товаров с остатками > 0 без external_id (не из 1С): {without_external_id}")
            self.stdout.write()
        
        # Товары с external_id, но неактивные
        with_external_id_inactive = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=False,
            external_id__isnull=False,
            external_id__gt=''
        ).count()
        if with_external_id_inactive > 0:
            self.stdout.write(f"⚠ В розничном каталоге товаров из 1С с остатками > 0, но неактивных: {with_external_id_inactive}")
            self.stdout.write()
        
        # Товары, которые должны показываться на сайте (с категорией, в активной категории, с правильным availability)
        retail_should_show = retail_with_stock_all.filter(
            category__isnull=False,
            category__is_active=True
        ).filter(
            Q(availability='in_stock') | Q(availability='order')
        ).count()
        
        self.stdout.write(f"Товаров в розничном каталоге, которые ДОЛЖНЫ показываться на сайте: {retail_should_show}")
        self.stdout.write(f"  (с категорией, в активной категории, availability='in_stock' или 'order')")
        self.stdout.write()
        
        # Проверяем, сколько товаров из 1С есть в оптовом каталоге, но нет в розничном
        # Это может объяснить разницу
        wholesale_with_external_id = Product.objects.filter(
            catalog_type='wholesale',
            quantity__gt=0,
            is_active=True,
            external_id__isnull=False,
            external_id__gt=''
        )
        
        retail_with_external_id = Product.objects.filter(
            catalog_type='retail',
            quantity__gt=0,
            is_active=True,
            external_id__isnull=False,
            external_id__gt=''
        )
        
        # Находим external_id, которые есть в оптовом, но нет в розничном
        wholesale_external_ids = set(wholesale_with_external_id.values_list('external_id', flat=True))
        retail_external_ids = set(retail_with_external_id.values_list('external_id', flat=True))
        
        missing_in_retail = wholesale_external_ids - retail_external_ids
        if missing_in_retail:
            self.stdout.write(f"⚠ Товаров из 1С с остатками > 0 есть в ОПТОВОМ каталоге, но НЕТ в РОЗНИЧНОМ: {len(missing_in_retail)}")
            self.stdout.write(f"  Это может объяснить разницу в количестве товаров")
            # Показываем примеры
            examples = wholesale_with_external_id.filter(external_id__in=list(missing_in_retail)[:5])
            for p in examples:
                self.stdout.write(f"    * {p.name[:50]} (артикул: {p.article}, external_id: {p.external_id}, количество: {p.quantity})")
            self.stdout.write()
        
        # Рекомендации
        self.stdout.write("=" * 80)
        self.stdout.write("РЕКОМЕНДАЦИИ")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if retail_no_category > 0:
            self.stdout.write("1. Для исправления товаров без категории:")
            self.stdout.write("   python manage.py fix_missing_categories --catalog-type retail")
            self.stdout.write()
        
        if retail_in_inactive_category > 0:
            self.stdout.write("2. Для исправления товаров в неактивных категориях:")
            self.stdout.write("   python manage.py fix_missing_categories --catalog-type retail")
            self.stdout.write()
        
        if retail_out_of_stock > 0:
            self.stdout.write("3. Для исправления availability товаров с остатками:")
            self.stdout.write("   python manage.py restore_products_by_price --catalog-type retail")
            self.stdout.write()
        
        if missing_in_retail:
            self.stdout.write("4. Для создания товаров в розничном каталоге из оптового:")
            self.stdout.write("   python manage.py sync_retail_from_wholesale")
            self.stdout.write()
        
        if inactive_count > 0:
            self.stdout.write("5. Для активации неактивных товаров с остатками > 0:")
            self.stdout.write("   python manage.py restore_products_by_price")
            self.stdout.write()
        
        # Итоговая статистика
        self.stdout.write("ИТОГО:")
        self.stdout.write(f"  - Ожидается товаров: {expected_count}")
        self.stdout.write(f"  - Показывается на сайте: {retail_should_show}")
        self.stdout.write(f"  - Разница: {expected_count - retail_should_show}")
        self.stdout.write()
        
        if expected_count - retail_should_show > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠ Не хватает {expected_count - retail_should_show} товаров на сайте"
            ))
            self.stdout.write("  Возможные причины:")
            if retail_no_category > 0:
                self.stdout.write(f"    - {retail_no_category} товаров без категории")
            if retail_in_inactive_category > 0:
                self.stdout.write(f"    - {retail_in_inactive_category} товаров в неактивных категориях")
            if retail_out_of_stock > 0:
                self.stdout.write(f"    - {retail_out_of_stock} товаров с неправильным availability")
            if missing_in_retail:
                self.stdout.write(f"    - {len(missing_in_retail)} товаров есть только в оптовом каталоге")
            remaining = expected_count - retail_should_show - retail_no_category - retail_in_inactive_category - retail_out_of_stock - len(missing_in_retail) if missing_in_retail else 0
            if remaining > 0:
                self.stdout.write(f"    - {remaining} товаров по другим причинам (возможно, не были импортированы из 1С)")
        
        self.stdout.write()
        self.stdout.write("=" * 80)
