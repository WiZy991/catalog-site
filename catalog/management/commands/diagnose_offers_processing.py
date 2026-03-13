"""
Команда для диагностики обработки offers.xml.
Проверяет, почему товары не обрабатываются из offers.xml.
"""
from django.core.management.base import BaseCommand
from catalog.models import Product
from django.db.models import Q
import xml.etree.ElementTree as ET
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Диагностика обработки offers.xml'

    def add_arguments(self, parser):
        parser.add_argument(
            'filename',
            type=str,
            help='Имя файла offers.xml для анализа',
        )

    def handle(self, *args, **options):
        filename = options['filename']
        
        self.stdout.write("=" * 80)
        self.stdout.write("ДИАГНОСТИКА ОБРАБОТКИ OFFERS.XML")
        self.stdout.write("=" * 80)
        self.stdout.write()
        
        # Определяем путь к файлу
        exchange_dir = getattr(settings, 'ONE_C_EXCHANGE_DIR', os.path.join(settings.MEDIA_ROOT, '1c_exchange'))
        
        # Пробуем разные варианты имени файла
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
            
            # Анализируем первые 100 предложений
            analyzed = 0
            found_in_db = 0
            not_found_in_db = 0
            found_by_external_id = 0
            found_by_article = 0
            
            examples_not_found = []
            
            for idx, offer_elem in enumerate(offers[:100]):
                analyzed += 1
                
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
                
                # Ищем товар в базе
                product = Product.objects.filter(
                    Q(external_id=product_id) |
                    Q(external_id=product_base_id) |
                    Q(external_id__startswith=product_base_id + '#')
                ).first()
                
                if product:
                    found_in_db += 1
                    if product.external_id == product_id or product.external_id == product_base_id:
                        found_by_external_id += 1
                    else:
                        found_by_article += 1
                else:
                    not_found_in_db += 1
                    if len(examples_not_found) < 5:
                        # Извлекаем артикул для примера
                        article = None
                        article_elem = None
                        if namespace:
                            article_elem = offer_elem.find(f'.//{{{namespace}}}Артикул')
                        if article_elem is None:
                            article_elem = offer_elem.find('.//Артикул')
                        if article_elem is not None and article_elem.text:
                            article = article_elem.text.strip()
                        
                        examples_not_found.append({
                            'product_id': product_id,
                            'base_id': product_base_id,
                            'article': article
                        })
            
            # Дополнительная статистика по количеству и ценам
            offers_with_qty_gt_0 = 0
            offers_with_qty_eq_0 = 0
            offers_with_retail_price_gt_0 = 0
            offers_with_wholesale_price_gt_0 = 0
            
            for offer_elem in offers:
                # Количество
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
                
                if quantity is not None:
                    if quantity > 0:
                        offers_with_qty_gt_0 += 1
                    else:
                        offers_with_qty_eq_0 += 1
                
                # Цены
                prices_elem = None
                if namespace:
                    prices_elem = offer_elem.find(f'{{{namespace}}}Цены')
                if prices_elem is None:
                    prices_elem = offer_elem.find('Цены')
                
                if prices_elem is not None:
                    price_elems = []
                    if namespace:
                        price_elems = prices_elem.findall(f'{{{namespace}}}Цена')
                    if not price_elems:
                        price_elems = prices_elem.findall('Цена')
                    
                    for price_elem in price_elems:
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
                                        offers_with_retail_price_gt_0 += 1
                                        offers_with_wholesale_price_gt_0 += 1
                                        break
                            except (ValueError, AttributeError, TypeError):
                                pass
            
            self.stdout.write(f"Проанализировано предложений: {analyzed}")
            self.stdout.write(f"Найдено товаров в базе: {found_in_db}")
            self.stdout.write(f"  - По exact external_id: {found_by_external_id}")
            self.stdout.write(f"  - По base_id или артикулу: {found_by_article}")
            self.stdout.write(f"Не найдено товаров в базе: {not_found_in_db}")
            self.stdout.write()
            self.stdout.write("Статистика по количеству и ценам в offers.xml:")
            self.stdout.write(f"  - Предложений с Количество > 0: {offers_with_qty_gt_0}")
            self.stdout.write(f"  - Предложений с Количество = 0: {offers_with_qty_eq_0}")
            self.stdout.write(f"  - Предложений с ценой > 0 (по данным ЦенаЗаЕдиницу): {offers_with_retail_price_gt_0}")
            self.stdout.write()
            
            if examples_not_found:
                self.stdout.write("Примеры товаров, которые НЕ найдены в базе:")
                for ex in examples_not_found:
                    self.stdout.write(f"  - Ид: {ex['product_id']}, base_id: {ex['base_id']}, артикул: {ex['article']}")
                    
                    # Проверяем, есть ли товар с таким артикулом
                    if ex['article']:
                        by_article = Product.objects.filter(article=ex['article']).first()
                        if by_article:
                            self.stdout.write(f"    → Найден товар с таким артикулом: external_id={by_article.external_id}, каталог={by_article.catalog_type}")
                    self.stdout.write()
            
            # Статистика по товарам в базе
            total_products = Product.objects.filter(
                external_id__isnull=False,
                external_id__gt=''
            ).count()
            
            self.stdout.write("=" * 80)
            self.stdout.write("СТАТИСТИКА")
            self.stdout.write("=" * 80)
            self.stdout.write()
            self.stdout.write(f"Всего товаров в базе с external_id: {total_products}")
            self.stdout.write(f"Предложений в offers.xml: {len(offers)}")
            self.stdout.write(f"Процент совпадений (из первых 100): {found_in_db}%")
            self.stdout.write()
            
            if not_found_in_db > 50:
                self.stdout.write(self.style.WARNING(
                    "⚠ ПРОБЛЕМА: Большинство товаров из offers.xml не найдены в базе!"
                ))
                self.stdout.write("Возможные причины:")
                self.stdout.write("  1. Товары не были созданы из import.xml")
                self.stdout.write("  2. external_id в offers.xml не совпадает с external_id в import.xml")
                self.stdout.write("  3. Товары были удалены или не импортированы")
                self.stdout.write()
                self.stdout.write("РЕКОМЕНДАЦИЯ: Проверьте логи обмена import.xml")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка при анализе файла: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write()
        self.stdout.write("=" * 80)
