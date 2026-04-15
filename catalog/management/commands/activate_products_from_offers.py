"""
Команда для активации товаров из offers.xml.
Проверяет файл offers.xml и активирует товары, которые должны быть активны.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product
from django.db.models import Q
from django.db import transaction
import xml.etree.ElementTree as ET
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Активирует товары из offers.xml, которые должны быть активны'

    def add_arguments(self, parser):
        parser.add_argument(
            'filename',
            type=str,
            help='Имя файла offers.xml',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет активировано, без фактической активации',
        )

    def handle(self, *args, **options):
        filename = options['filename']
        dry_run = options['dry_run']
        
        self.stdout.write("=" * 80)
        self.stdout.write("АКТИВАЦИЯ ТОВАРОВ ИЗ OFFERS.XML")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОВЕРКИ (dry-run) - товары НЕ будут активированы"))
            self.stdout.write()
        
        # Определяем путь к файлу
        exchange_dir = getattr(settings, 'ONE_C_EXCHANGE_DIR', os.path.join(settings.MEDIA_ROOT, '1c_exchange'))
        
        possible_paths = [
            os.path.join(exchange_dir, filename),
            os.path.join(exchange_dir, filename + '.xml'),
            os.path.join(exchange_dir, filename.replace('.xml', '')),
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            self.stdout.write(self.style.ERROR(f"Файл не найден: {filename}"))
            return
        
        self.stdout.write(f"Анализируем файл: {file_path}")
        self.stdout.write()
        
        try:
            # Парсим XML
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Находим namespace
            namespaces = {}
            if root.tag.startswith('{'):
                namespace = root.tag[1:].split('}')[0]
                namespaces[''] = namespace
                namespaces['cml'] = namespace
                namespaces['cml2'] = namespace
            
            # Ищем предложения
            namespace = namespaces.get('', namespaces.get('cml', namespaces.get('cml2', None)))
            offers = []
            if namespace:
                offers = root.findall(f'.//{{{namespace}}}Предложение')
                if not offers:
                    package = root.find(f'.//{{{namespace}}}ПакетПредложений')
                    if package is not None:
                        offers = package.findall(f'.//{{{namespace}}}Предложение')
            if not offers:
                offers = root.findall('.//Предложение')
                if not offers:
                    package = root.find('.//ПакетПредложений')
                    if package is not None:
                        offers = package.findall('.//Предложение')
            
            self.stdout.write(f"Найдено предложений в XML: {len(offers)}")
            self.stdout.write()
            
            # ID типов цен
            RETAIL_PRICE_TYPE_ID = 'f6708032-0bd5-11f1-811f-00155d01d802'
            WHOLESALE_PRICE_TYPE_ID = 'b12f44c0-1208-11f1-811f-00155d01d802'
            
            activated_retail = 0
            activated_wholesale = 0
            not_found = 0
            
            with transaction.atomic():
                for idx, offer_elem in enumerate(offers):
                    # Извлекаем Ид товара
                    product_id_elem = None
                    if namespace:
                        product_id_elem = offer_elem.find(f'{{{namespace}}}Ид')
                    if product_id_elem is None:
                        product_id_elem = offer_elem.find('Ид')
                    
                    if product_id_elem is None or not product_id_elem.text:
                        continue
                    
                    product_id = product_id_elem.text.strip()
                    product_base_id = product_id.split('#')[0] if '#' in product_id else product_id
                    
                    # Извлекаем количество
                    quantity = None
                    quantity_elem = None
                    if namespace:
                        quantity_elem = offer_elem.find(f'{{{namespace}}}Количество')
                    if quantity_elem is None:
                        quantity_elem = offer_elem.find('Количество')
                    
                    if quantity_elem is not None and quantity_elem.text:
                        try:
                            quantity = int(float(quantity_elem.text.strip().replace(',', '.')))
                        except (ValueError, AttributeError):
                            quantity = None
                    
                    if quantity is None or quantity == 0:
                        continue  # Пропускаем товары без остатка
                    
                    # Извлекаем цены
                    prices_elem = None
                    if namespace:
                        prices_elem = offer_elem.find(f'{{{namespace}}}Цены')
                    if prices_elem is None:
                        prices_elem = offer_elem.find('Цены')
                    
                    retail_price = None
                    wholesale_price = None
                    
                    if prices_elem is not None:
                        price_elems = []
                        if namespace:
                            price_elems = prices_elem.findall(f'{{{namespace}}}Цена')
                        if not price_elems:
                            price_elems = prices_elem.findall('Цена')
                        
                        for price_elem in price_elems:
                            price_type_id_elem = None
                            if namespace:
                                price_type_id_elem = price_elem.find(f'{{{namespace}}}ИдТипаЦены')
                            if price_type_id_elem is None:
                                price_type_id_elem = price_elem.find('ИдТипаЦены')
                            
                            if price_type_id_elem is not None and price_type_id_elem.text:
                                price_type_id = price_type_id_elem.text.strip()
                                
                                price_value_elem = None
                                if namespace:
                                    price_value_elem = price_elem.find(f'{{{namespace}}}ЦенаЗаЕдиницу')
                                if price_value_elem is None:
                                    price_value_elem = price_elem.find('ЦенаЗаЕдиницу')
                                
                                if price_value_elem is not None and price_value_elem.text:
                                    try:
                                        price_str = price_value_elem.text.strip().replace(',', '.').replace(' ', '').replace('\xa0', '')
                                        if price_str:
                                            price = float(price_str)
                                            if price > 0:
                                                if price_type_id == RETAIL_PRICE_TYPE_ID:
                                                    retail_price = price
                                                elif price_type_id == WHOLESALE_PRICE_TYPE_ID:
                                                    wholesale_price = price
                                    except (ValueError, AttributeError, TypeError):
                                        pass
                    
                    # Если нет цены или количества, пропускаем
                    if not retail_price and not wholesale_price:
                        continue
                    
                    # Ищем товары в обоих каталогах
                    for catalog_type in ['retail', 'wholesale']:
                        product = Product.objects.filter(
                            Q(external_id=product_id) |
                            Q(external_id=product_base_id) |
                            Q(external_id__startswith=product_base_id + '#')
                        ).filter(
                            catalog_type=catalog_type
                        ).first()
                        
                        if not product:
                            # Пробуем по артикулу
                            product = Product.objects.filter(
                                article=product_base_id,
                                catalog_type=catalog_type
                            ).first()
                        
                        if product:
                            # Обновляем товар
                            should_activate = False
                            
                            if catalog_type == 'retail' and retail_price:
                                # ВАЖНО: Обновляем всегда, если есть цена и количество
                                if not dry_run:
                                    product.price = retail_price
                                    product.quantity = quantity
                                    product.is_active = quantity > 0
                                    product.availability = 'in_stock' if quantity > 0 else 'out_of_stock'
                                    product.save(update_fields=['price', 'quantity', 'is_active', 'availability'])
                                activated_retail += 1
                                should_activate = True
                            elif catalog_type == 'wholesale' and wholesale_price:
                                # ВАЖНО: Обновляем всегда, если есть цена и количество
                                if not dry_run:
                                    product.wholesale_price = wholesale_price
                                    product.quantity = quantity
                                    product.is_active = quantity > 0
                                    product.availability = 'in_stock' if quantity > 0 else 'out_of_stock'
                                    product.save(update_fields=['wholesale_price', 'quantity', 'is_active', 'availability'])
                                activated_wholesale += 1
                                should_activate = True
                            
                            if should_activate and activated_retail + activated_wholesale <= 10:
                                price_info = f"цена: {retail_price if catalog_type == 'retail' else wholesale_price}"
                                self.stdout.write(f"  ✓ {product.name[:50]} ({catalog_type}): количество: {quantity}, {price_info}, external_id: {product.external_id[:50] if product.external_id else 'нет'}")
                        else:
                            # ВАЖНО: Логируем товары, которые не найдены
                            if not_found < 20:
                                # Проверяем, есть ли товар с таким external_id в любом каталоге
                                any_product = Product.objects.filter(
                                    Q(external_id=product_id) |
                                    Q(external_id=product_base_id) |
                                    Q(external_id__startswith=product_base_id + '#')
                                ).first()
                                if any_product:
                                    self.stdout.write(f"  ⚠ Товар найден в каталоге {any_product.catalog_type}, но нужен {catalog_type}: Ид={product_id}, external_id={any_product.external_id}")
                                else:
                                    self.stdout.write(f"  ⚠ Товар не найден вообще: Ид={product_id}, base_id={product_base_id}, каталог={catalog_type}")
                            not_found += 1
            
            self.stdout.write()
            self.stdout.write("=" * 80)
            self.stdout.write("РЕЗУЛЬТАТ")
            self.stdout.write("=" * 80)
            self.stdout.write()
            
            if not dry_run:
                self.stdout.write(self.style.SUCCESS(f"✓ Активировано товаров в розничном каталоге: {activated_retail}"))
                self.stdout.write(self.style.SUCCESS(f"✓ Активировано товаров в оптовом каталоге: {activated_wholesale}"))
            else:
                self.stdout.write(f"Будет активировано товаров в розничном каталоге: {activated_retail}")
                self.stdout.write(f"Будет активировано товаров в оптовом каталоге: {activated_wholesale}")
            
            if not_found > 0:
                self.stdout.write(self.style.WARNING(f"⚠ Товаров не найдено в базе: {not_found}"))
            
            self.stdout.write()
            self.stdout.write("Проверьте результат:")
            self.stdout.write("  python manage.py check_products_status")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка при обработке файла: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write()
        self.stdout.write("=" * 80)
