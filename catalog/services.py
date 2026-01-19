"""
Сервисы автоматизации для каталога товаров.
"""
import re
import os
from django.core.files.base import ContentFile
from django.db import transaction
from .models import Category, Product, ProductImage, Brand


# Ключевые слова для автоматического определения категорий
CATEGORY_KEYWORDS = {
    'Двигатель': ['двигатель', 'мотор', 'движок', 'engine', 'дизель', 'бензиновый'],
    'Стартеры': ['стартер', 'starter', 'пускатель'],
    'Генераторы': ['генератор', 'generator', 'альтернатор'],
    'Турбины': ['турбина', 'турбокомпрессор', 'turbo', 'турбонаддув'],
    'Топливная система': ['форсунка', 'тнвд', 'насос топливный', 'инжектор', 'fuel'],
    'Фильтры': ['фильтр', 'filter', 'воздушный', 'масляный', 'топливный'],
    'Тормозная система': ['тормоз', 'колодки', 'диск тормозной', 'суппорт', 'brake'],
    'Подвеска': ['амортизатор', 'пружина', 'рычаг', 'сайлентблок', 'подшипник ступицы'],
    'Трансмиссия': ['кпп', 'коробка передач', 'сцепление', 'редуктор', 'transmission'],
    'Электрика': ['датчик', 'реле', 'проводка', 'блок управления', 'sensor'],
    'Кузов': ['бампер', 'крыло', 'капот', 'дверь', 'фара', 'зеркало'],
    'Охлаждение': ['радиатор', 'термостат', 'помпа', 'вентилятор', 'cooling'],
    'Шины и диски': ['шина', 'диск', 'колесо', 'покрышка', 'tire', 'wheel'],
    'Масла и жидкости': ['масло', 'антифриз', 'тормозная жидкость', 'oil'],
}

# Маппинг ключевых слов товаров на названия подкатегорий
SUBCATEGORY_KEYWORDS = {
    'амортизатор': 'Амортизаторы',
    'пружина': 'Пружины',
    'рычаг': 'Рычаги',
    'сайлентблок': 'Сайлентблоки',
    'подшипник ступицы': 'Подшипники ступицы',
    'стартер': 'Стартеры',
    'генератор': 'Генераторы',
    'турбина': 'Турбины',
    'форсунка': 'Форсунки',
    'тнвд': 'ТНВД',
    'насос топливный': 'Топливные насосы',
    'фильтр': 'Фильтры',
    'тормоз': 'Тормозные колодки',
    'колодки': 'Тормозные колодки',
    'диск тормозной': 'Тормозные диски',
    'суппорт': 'Суппорты',
    'кпп': 'КПП',
    'коробка передач': 'КПП',
    'сцепление': 'Сцепление',
    'редуктор': 'Редукторы',
    'датчик': 'Датчики',
    'реле': 'Реле',
    'радиатор': 'Радиаторы',
    'термостат': 'Термостаты',
    'помпа': 'Помпы',
    'вентилятор': 'Вентиляторы',
}

# Известные бренды для автоопределения
KNOWN_BRANDS = [
    'Toyota', 'Isuzu', 'Hino', 'Mitsubishi', 'Nissan', 'Mazda', 'Honda', 'Suzuki',
    'Hyundai', 'Kia', 'Daewoo', 'Ssangyong', 'Volvo', 'Scania', 'MAN', 'Mercedes',
    'DAF', 'Iveco', 'Renault', 'Ford', 'Chevrolet', 'Bosch', 'Denso', 'Aisin',
    'NGK', 'KYB', 'Monroe', 'Sachs', 'LUK', 'INA', 'SKF', 'NTN', 'Koyo', 'NSK',
    'Mobis', 'Mando', 'CTR', 'GMB', 'NPR', 'Mahle', 'Knecht', 'Mann', 'Filtron',
    # Бренды из файла клиента
    'DAIHATSU', 'INFINITI', 'HONDA', 'ISUZU', 'KIA',
]


def detect_category(text):
    """
    Автоматически определяет категорию по ключевым словам в тексте.
    Возвращает название категории или None.
    """
    text_lower = text.lower()
    
    for category_name, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return category_name
    
    return None


def detect_brand(text):
    """
    Автоматически определяет бренд по тексту.
    """
    text_upper = text.upper()
    
    for brand in KNOWN_BRANDS:
        if brand.upper() in text_upper:
            return brand
    
    return None


def extract_article(text):
    """
    Извлекает артикул из текста.
    Артикул обычно содержит буквы и цифры, например: 23300-78090, ME220745, 1-13200-469-0
    """
    # Паттерны для артикулов (в порядке приоритета)
    patterns = [
        r'\b(\d{5}-\d{5})\b',  # Toyota style: 23300-78090
        r'\b([A-Z]{2}\d{6})\b',  # Mitsubishi style: ME220745
        r'\b(\d-\d{5}-\d{3}-\d)\b',  # Isuzu style: 1-13200-469-0
        r'\b(\d{6})\b',  # 6-digit codes: 332120, 331008
        r'\b([A-Z0-9\-]{6,20})\b',  # Generic alphanumeric with dashes
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).upper()
            # Исключаем известные бренды
            if candidate not in [b.upper() for b in KNOWN_BRANDS]:
                return candidate
    
    return None


def parse_product_name(name):
    """
    Парсит название товара и извлекает данные.
    Возвращает словарь с полями: brand, article, category, clean_name, oem_number, applicability
    
    Поддерживает формат: "Амортизатор DAIHATSU 332120 /48510-B1020 M300/M301 F/R/L 2WD"
    """
    result = {
        'brand': None,
        'article': None,
        'category': None,
        'clean_name': name,
        'oem_number': None,
        'applicability': None,
    }
    
    # Определяем категорию
    result['category'] = detect_category(name)
    
    # Определяем бренд
    result['brand'] = detect_brand(name)
    
    # Ищем OEM номер (формат: /48510-B1020 или /51601-S5P-G03)
    # В формате клиента: "Амортизатор, DAIHATSU 332120 /48510-B1020 M300/M301..."
    oem_match = re.search(r'\s+/([A-Z0-9\-]+)', name)
    if oem_match:
        result['oem_number'] = oem_match.group(1)
    
    # Извлекаем артикул (6-значное число после бренда, перед OEM номером)
    # Формат клиента: "Амортизатор, DAIHATSU 332120 /48510-B1020..."
    # Артикул: 332120 - это число сразу после бренда, перед слешем
    
    if result['brand']:
        # Ищем паттерн: бренд + пробел/запятая + число (артикул)
        brand_escaped = re.escape(result['brand'])
        article_match = re.search(rf'\b{brand_escaped}[,\s]+(\d{{6}})\b', name, re.IGNORECASE)
        if article_match:
            result['article'] = article_match.group(1)
    
    # Если не нашли через бренд, ищем 6-значные числа до слеша
    if not result['article']:
        before_oem = name.split('/')[0] if '/' in name else name
        # Ищем 6-значные числа (формат артикулов в файле клиента: 332120, 333433 и т.д.)
        article_matches = re.findall(r'\b(\d{6})\b', before_oem)
        if article_matches:
            # Берем последнее найденное число (обычно это артикул, а не часть модели)
            for match in reversed(article_matches):
                # Исключаем числа, которые могут быть частью других кодов
                if match not in ['202512', '202518', '202425']:  # Исключаем даты
                    result['article'] = match
                    break
    
    # Если все еще не нашли, пробуем стандартный метод
    if not result['article']:
        result['article'] = extract_article(name)
    
    # Извлекаем применимость (часть после OEM номера)
    # Формат: "Амортизатор, DAIHATSU 332120 /48510-B1020 M300/M301 F/R/L 2WD"
    # Применимость: "M300/M301 F/R/L 2WD" (все после OEM номера)
    if '/' in name:
        parts = name.split('/', 1)
        if len(parts) > 1:
            after_slash = parts[1].strip()
            # Находим конец OEM номера (первый пробел после слеша)
            oem_end_match = re.search(r'^([A-Z0-9\-]+)\s+', after_slash)
            if oem_end_match:
                # Берем все что после OEM номера
                applicability_part = after_slash[len(oem_end_match.group(0)):].strip()
                # Очищаем от служебных слов, но оставляем технические характеристики
                applicability_part = re.sub(r'\b(НОВЫЙ|NEW)\b', '', applicability_part, flags=re.IGNORECASE)
                applicability_part = applicability_part.strip()
                if applicability_part:
                    result['applicability'] = applicability_part
            else:
                # Если не нашли пробел, значит все что после слеша - это применимость
                applicability_part = after_slash.strip()
                if applicability_part:
                    result['applicability'] = applicability_part
    
    return result


def detect_subcategory(product_name, parent_category):
    """
    Определяет подкатегорию на основе названия товара и родительской категории.
    """
    if not parent_category or not product_name:
        return None
    
    product_name_lower = product_name.lower()
    
    # Ищем ключевые слова в названии товара
    for keyword, subcategory_name in SUBCATEGORY_KEYWORDS.items():
        if keyword.lower() in product_name_lower:
            return subcategory_name
    
    return None


def get_or_create_category(category_name, parent=None):
    """
    Получает или создаёт категорию по названию.
    """
    if not category_name:
        return None
    
    category, created = Category.objects.get_or_create(
        name=category_name,
        parent=parent,
        defaults={'is_active': True}
    )
    
    return category


def get_or_create_subcategory(product_name, parent_category):
    """
    Получает или создаёт подкатегорию на основе названия товара.
    Если товар "амортизатор" и категория "Подвеска", создаст подкатегорию "Амортизаторы".
    """
    if not parent_category or not product_name:
        return parent_category
    
    # Определяем название подкатегории
    subcategory_name = detect_subcategory(product_name, parent_category)
    
    if not subcategory_name:
        return parent_category
    
    # Создаем или получаем подкатегорию
    subcategory, created = Category.objects.get_or_create(
        name=subcategory_name,
        parent=parent_category,
        defaults={'is_active': True}
    )
    
    return subcategory


def process_bulk_import(data_rows, auto_category=True, auto_brand=True):
    """
    Массовый импорт товаров с автоматизацией.
    
    data_rows: список словарей с данными товаров
    auto_category: автоматически определять категорию
    auto_brand: автоматически определять бренд
    
    Возвращает статистику импорта.
    """
    stats = {
        'total': len(data_rows),
        'created': 0,
        'updated': 0,
        'errors': 0,
        'error_details': [],
    }
    
    with transaction.atomic():
        for i, row in enumerate(data_rows, 1):
            try:
                # Получаем название товара из поля 'name'
                name = str(row.get('name', '')).strip()
                
                if not name or name.lower() in ['none', 'null', '']:
                    stats['errors'] += 1
                    stats['error_details'].append(f'Строка {i}: пустое название товара')
                    continue
                
                # Парсим название
                parsed = parse_product_name(name)
                
                # Определяем артикул (из колонки Артикул или из названия)
                article = str(row.get('article', '')).strip()
                # Если артикул не указан в отдельной колонке, пытаемся извлечь из названия
                if not article and parsed['article']:
                    article = parsed['article']
                
                # Определяем бренд
                if auto_brand:
                    brand = row.get('brand', '').strip() or parsed['brand'] or ''
                else:
                    brand = row.get('brand', '').strip()
                
                # Определяем категорию
                category = None
                if auto_category:
                    category_name = row.get('category', '').strip() or parsed['category']
                    if category_name:
                        parent_category = get_or_create_category(category_name)
                        # Автоматически создаем подкатегорию на основе названия товара
                        category = get_or_create_subcategory(name, parent_category)
                elif row.get('category'):
                    parent_category = get_or_create_category(row['category'])
                    # Автоматически создаем подкатегорию на основе названия товара
                    category = get_or_create_subcategory(name, parent_category)
                
                # Обрабатываем цену
                # Формат может быть: "2 000,00" (пробел - тысячи, запятая - десятичные) или просто число
                price_value = 0
                # Сначала проверяем числовое значение (если было сохранено)
                if row.get('price_num') is not None:
                    try:
                        price_value = float(row['price_num'])
                    except (ValueError, TypeError):
                        price_value = 0
                elif row.get('price'):
                    price_str = str(row['price']).strip()
                    if price_str and price_str.lower() not in ['none', 'null', '']:
                        # Убираем все пробелы и неразрывные пробелы (разделители тысяч)
                        price_str = price_str.replace(' ', '').replace('\xa0', '').replace('\u00A0', '').replace('\u2009', '').replace('\u202F', '')
                        # Заменяем запятую на точку для десятичного разделителя
                        price_str = price_str.replace(',', '.')
                        try:
                            price_value = float(price_str)
                        except (ValueError, TypeError):
                            price_value = 0
                
                # Обрабатываем остаток на складе
                # Формат: "4,000" или "4 000" (запятая/пробел как разделитель тысяч) - это целое число
                quantity_value = 0
                # Сначала проверяем числовое значение (если было сохранено)
                if row.get('quantity_num') is not None:
                    try:
                        quantity_value = int(float(row['quantity_num']))
                    except (ValueError, TypeError):
                        quantity_value = 0
                # Также проверяем альтернативные ключи для остатка
                elif row.get('остаток_num') is not None:
                    try:
                        quantity_value = int(float(row['остаток_num']))
                    except (ValueError, TypeError):
                        quantity_value = 0
                elif row.get('quantity') or row.get('остаток'):
                    quantity_str = str(row.get('quantity') or row.get('остаток', '')).strip()
                    if quantity_str and quantity_str.lower() not in ['none', 'null', '']:
                        # Убираем все разделители тысяч (пробелы и запятые)
                        quantity_str = quantity_str.replace(' ', '').replace('\xa0', '').replace('\u00A0', '').replace('\u2009', '').replace('\u202F', '').replace(',', '')
                        try:
                            # Преобразуем в float на случай если есть точка, потом в int
                            quantity_value = int(float(quantity_str))
                        except (ValueError, TypeError):
                            quantity_value = 0
                
                # Проверяем существует ли товар (по артикулу или названию)
                product = None
                if article:
                    product = Product.objects.filter(article=article).first()
                
                if not product:
                    product = Product.objects.filter(name=name).first()
                
                # Определяем применимость (из парсинга или из колонки)
                applicability = row.get('applicability', '').strip()
                if not applicability and parsed.get('applicability'):
                    applicability = parsed['applicability']
                
                # Формируем характеристики из OEM номера если есть
                characteristics = row.get('characteristics', '').strip()
                if parsed.get('oem_number') and not characteristics:
                    characteristics = f"OEM: {parsed['oem_number']}"
                
                # Определяем наличие на основе остатка
                availability = row.get('availability', 'in_stock')
                if quantity_value == 0:
                    availability = 'out_of_stock'
                elif quantity_value > 0:
                    availability = 'in_stock'
                
                if product:
                    # Обновляем существующий
                    product.name = name
                    if brand:
                        product.brand = brand
                    if category:
                        product.category = category
                    if price_value > 0:
                        product.price = price_value
                    if row.get('description'):
                        product.description = row['description']
                    if row.get('short_description'):
                        product.short_description = row['short_description']
                    if applicability:
                        product.applicability = applicability
                    if row.get('cross_numbers'):
                        product.cross_numbers = row['cross_numbers']
                    if characteristics:
                        product.characteristics = characteristics
                    if row.get('farpost_url'):
                        product.farpost_url = row['farpost_url']
                    if quantity_value >= 0:
                        product.quantity = quantity_value
                    product.availability = availability
                    product.save()
                    stats['updated'] += 1
                else:
                    # Создаём новый
                    product = Product.objects.create(
                        name=name,
                        article=article,
                        brand=brand,
                        category=category,
                        price=price_value,
                        description=row.get('description', ''),
                        short_description=row.get('short_description', ''),
                        applicability=applicability,
                        cross_numbers=row.get('cross_numbers', ''),
                        characteristics=characteristics,
                        farpost_url=row.get('farpost_url', ''),
                        condition=row.get('condition', 'new'),
                        availability=availability,
                        quantity=quantity_value,
                        is_active=True,
                    )
                    stats['created'] += 1
                    
            except Exception as e:
                stats['errors'] += 1
                stats['error_details'].append(f'Строка {i}: {str(e)}')
    
    return stats


def match_image_to_product(filename):
    """
    Находит товар по имени файла изображения.
    Имя файла может содержать артикул или часть названия.
    
    Примеры:
    - 23300-78090.jpg -> товар с артикулом 23300-78090
    - ME220745_1.jpg -> товар с артикулом ME220745
    - starter_isuzu.jpg -> поиск по ключевым словам
    """
    # Убираем расширение и номер фото
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[_-]?\d*$', '', name)  # Убираем _1, _2, -1 в конце
    name = name.replace('_', ' ').replace('-', ' ')
    
    # Пробуем найти по артикулу (точное совпадение)
    product = Product.objects.filter(article__iexact=name.replace(' ', '-')).first()
    if product:
        return product
    
    product = Product.objects.filter(article__iexact=name.replace(' ', '')).first()
    if product:
        return product
    
    # Пробуем найти по артикулу (частичное совпадение)
    article = extract_article(name)
    if article:
        product = Product.objects.filter(article__icontains=article).first()
        if product:
            return product
    
    # Поиск по названию
    words = name.split()
    if len(words) >= 2:
        # Ищем товары, содержащие все слова из имени файла
        products = Product.objects.all()
        for word in words:
            if len(word) > 2:
                products = products.filter(name__icontains=word)
        
        product = products.first()
        if product:
            return product
    
    return None


def process_bulk_images(images, create_products=False):
    """
    Массовая загрузка изображений с автоматической привязкой к товарам.
    
    images: список кортежей (filename, file_content)
    create_products: создавать товары, если не найдены
    
    Возвращает статистику.
    """
    stats = {
        'total': len(images),
        'matched': 0,
        'created_products': 0,
        'not_matched': 0,
        'not_matched_files': [],
    }
    
    for filename, file_content in images:
        product = match_image_to_product(filename)
        
        if not product and create_products:
            # Создаём товар из имени файла
            name = os.path.splitext(filename)[0]
            name = re.sub(r'[_-]?\d*$', '', name)
            name = name.replace('_', ' ').replace('-', ' ').title()
            
            parsed = parse_product_name(name)
            category = get_or_create_category(parsed['category']) if parsed['category'] else None
            
            product = Product.objects.create(
                name=name,
                article=parsed['article'] or '',
                brand=parsed['brand'] or '',
                category=category,
                is_active=True,
            )
            stats['created_products'] += 1
        
        if product:
            # Создаём изображение
            is_main = not product.images.exists()
            
            img = ProductImage(
                product=product,
                is_main=is_main,
            )
            img.image.save(filename, ContentFile(file_content), save=True)
            stats['matched'] += 1
        else:
            stats['not_matched'] += 1
            stats['not_matched_files'].append(filename)
    
    return stats


def generate_product_title(product):
    """
    Автоматически генерирует заголовок товара для SEO.
    """
    parts = []
    
    # Определяем тип товара
    category_name = detect_category(product.name)
    if category_name:
        parts.append(category_name)
    
    # Добавляем бренд
    if product.brand:
        parts.append(product.brand)
    
    # Добавляем артикул
    if product.article:
        parts.append(product.article)
    
    # Если ничего не собрали, используем название
    if not parts:
        return product.name
    
    return ' '.join(parts)


def generate_farpost_title(product):
    """
    Генерирует заголовок для Farpost согласно ТЗ.
    Формат: Бренд + Артикул + Краткая характеристика
    Пример: "Starter Isuzu 10PD1 / 12PD1, 24V — оригинал"
    """
    parts = []
    
    # Определяем тип товара из категории или названия
    category_name = detect_category(product.name)
    if category_name:
        parts.append(category_name.rstrip('ы'))  # Стартеры -> Стартер
    
    # Добавляем бренд
    if product.brand:
        parts.append(product.brand)
    
    # Добавляем артикул если есть
    if product.article:
        parts.append(product.article)
    
    # Если ничего не собрали, используем название
    if not parts:
        return product.name
    
    return ' '.join(parts)


def generate_farpost_description(product, site_url=''):
    """
    Генерирует полное описание для Farpost согласно ТЗ.
    Включает все необходимые данные.
    """
    from django.urls import reverse
    
    lines = []
    
    # Основное описание
    if product.short_description:
        lines.append(product.short_description)
    elif product.description:
        # Берем первые 200 символов описания
        desc = product.description[:200].strip()
        if len(product.description) > 200:
            desc += '...'
        lines.append(desc)
    
    lines.append('')
    
    # Структурированные данные
    if product.brand:
        lines.append(f'Бренд: {product.brand}')
    
    if product.article:
        lines.append(f'Артикул: {product.article}')
    
    # Характеристики
    if product.characteristics:
        lines.append('')
        lines.append('Характеристики:')
        char_list = product.get_characteristics_list()
        for key, value in char_list:
            lines.append(f'{key}: {value}')
    
    # Применимость
    if product.applicability:
        lines.append('')
        lines.append('Применимость:')
        applicability_list = product.get_applicability_list()
        for item in applicability_list:
            lines.append(f'- {item}')
    
    # Кросс-номера
    if product.cross_numbers:
        lines.append('')
        lines.append('Кросс-номера (аналоги):')
        cross_list = product.get_cross_numbers_list()
        lines.append(', '.join(cross_list))
    
    # Ссылка на сайт
    if site_url:
        lines.append('')
        lines.append(f'Подробнее на сайте: {site_url}')
    
    lines.append('')
    lines.append(f'Цена: {product.price} руб.')
    lines.append(f'Наличие: {product.get_availability_display()}')
    if product.condition:
        lines.append(f'Состояние: {product.get_condition_display()}')
    
    return '\n'.join(lines)


def generate_farpost_images(product, request=None):
    """
    Генерирует список ссылок на изображения для Farpost.
    """
    images = product.images.all().order_by('-is_main', 'order')[:5]  # Максимум 5 фото
    
    image_urls = []
    for img in images:
        if img.image:
            if request:
                url = request.build_absolute_uri(img.image.url)
            else:
                # Без request используем относительный путь
                url = img.image.url
            image_urls.append(url)
    
    return image_urls


def generate_farpost_api_file(products, file_format='xls', request=None):
    """
    Генерирует файл для отправки в API Farpost.
    
    products: QuerySet или список товаров
    file_format: 'xls', 'csv' или 'xml'
    request: объект запроса Django для генерации абсолютных URL изображений
    
    Возвращает: (file_content, filename, content_type)
    """
    import io
    import csv
    from datetime import datetime
    
    if file_format == 'csv':
        # CSV формат
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Заголовки (адаптируйте под формат Farpost)
        writer.writerow([
            'Название', 'Цена', 'Описание', 'Артикул', 'Бренд',
            'Состояние', 'Наличие', 'Характеристики', 'Применимость',
            'Кросс-номера', 'Фото1', 'Фото2', 'Фото3', 'Фото4', 'Фото5',
            'Ссылка на сайт', 'Категория'
        ])
        
        for product in products:
            title = generate_farpost_title(product)
            site_url = request.build_absolute_uri(product.get_absolute_url()) if request else ''
            description = generate_farpost_description(product, site_url)
            photo_urls = generate_farpost_images(product, request)
            
            # Дополняем до 5 фото
            while len(photo_urls) < 5:
                photo_urls.append('')
            
            characteristics = ''
            if product.characteristics:
                char_list = product.get_characteristics_list()
                characteristics = '\n'.join([f'{k}: {v}' for k, v in char_list])
            
            writer.writerow([
                title,
                str(product.price),
                description,
                product.article or '',
                product.brand or '',
                product.get_condition_display(),
                product.get_availability_display(),
                characteristics,
                product.applicability or '',
                product.cross_numbers or '',
                photo_urls[0],
                photo_urls[1],
                photo_urls[2],
                photo_urls[3],
                photo_urls[4],
                site_url,
                product.category.name if product.category else '',
            ])
        
        content = output.getvalue().encode('utf-8-sig')
        filename = f'farpost_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        content_type = 'text/csv; charset=utf-8-sig'
        return content, filename, content_type
    
    elif file_format == 'xls':
        # XLS формат (используем openpyxl, так как он уже в проекте)
        from openpyxl import Workbook
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Товары'
        
        # Заголовки
        headers = [
            'Название', 'Цена', 'Описание', 'Артикул', 'Бренд',
            'Состояние', 'Наличие', 'Характеристики', 'Применимость',
            'Кросс-номера', 'Фото1', 'Фото2', 'Фото3', 'Фото4', 'Фото5',
            'Ссылка на сайт', 'Категория'
        ]
        ws.append(headers)
        
        # Данные
        for product in products:
            title = generate_farpost_title(product)
            site_url = request.build_absolute_uri(product.get_absolute_url()) if request else ''
            description = generate_farpost_description(product, site_url)
            photo_urls = generate_farpost_images(product, request)
            
            # Дополняем до 5 фото
            while len(photo_urls) < 5:
                photo_urls.append('')
            
            characteristics = ''
            if product.characteristics:
                char_list = product.get_characteristics_list()
                characteristics = '\n'.join([f'{k}: {v}' for k, v in char_list])
            
            ws.append([
                title,
                float(product.price),
                description,
                product.article or '',
                product.brand or '',
                product.get_condition_display(),
                product.get_availability_display(),
                characteristics,
                product.applicability or '',
                product.cross_numbers or '',
                photo_urls[0],
                photo_urls[1],
                photo_urls[2],
                photo_urls[3],
                photo_urls[4],
                site_url,
                product.category.name if product.category else '',
            ])
        
        # Сохраняем в BytesIO
        output = io.BytesIO()
        wb.save(output)
        content = output.getvalue()
        filename = f'farpost_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xls'
        content_type = 'application/vnd.ms-excel'
        return content, filename, content_type
    
    elif file_format == 'xml':
        # XML формат
        from xml.etree.ElementTree import Element, SubElement, tostring
        from xml.dom import minidom
        
        root = Element('products')
        
        for product in products:
            product_elem = SubElement(root, 'product')
            
            title = generate_farpost_title(product)
            site_url = request.build_absolute_uri(product.get_absolute_url()) if request else ''
            description = generate_farpost_description(product, site_url)
            photo_urls = generate_farpost_images(product, request)
            
            SubElement(product_elem, 'title').text = title
            SubElement(product_elem, 'price').text = str(product.price)
            SubElement(product_elem, 'description').text = description
            SubElement(product_elem, 'article').text = product.article or ''
            SubElement(product_elem, 'brand').text = product.brand or ''
            SubElement(product_elem, 'condition').text = product.get_condition_display()
            SubElement(product_elem, 'availability').text = product.get_availability_display()
            
            if product.characteristics:
                char_elem = SubElement(product_elem, 'characteristics')
                char_list = product.get_characteristics_list()
                for key, value in char_list:
                    char_item = SubElement(char_elem, 'item')
                    SubElement(char_item, 'key').text = key
                    SubElement(char_item, 'value').text = value
            
            if product.applicability:
                SubElement(product_elem, 'applicability').text = product.applicability
            
            if product.cross_numbers:
                SubElement(product_elem, 'cross_numbers').text = product.cross_numbers
            
            photos_elem = SubElement(product_elem, 'photos')
            for url in photo_urls[:5]:
                if url:
                    SubElement(photos_elem, 'photo').text = url
            
            SubElement(product_elem, 'site_url').text = site_url
            if product.category:
                SubElement(product_elem, 'category').text = product.category.name
        
        # Форматируем XML
        rough_string = tostring(root, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
        
        filename = f'farpost_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
        content_type = 'application/xml; charset=utf-8'
        return pretty_xml, filename, content_type
    
    else:
        raise ValueError(f'Неподдерживаемый формат файла: {file_format}')


def sync_to_farpost_api(products, api_settings, file_format='xls', request=None):
    """
    Синхронизирует товары с API Farpost.
    
    products: QuerySet или список товаров
    api_settings: объект FarpostAPISettings
    file_format: 'xls', 'csv' или 'xml'
    request: объект запроса Django для генерации абсолютных URL изображений
    
    Возвращает: (success: bool, message: str, response_data: dict)
    """
    import requests
    import hashlib
    from django.conf import settings
    from django.utils import timezone
    
    try:
        # Генерируем файл
        file_content, filename, content_type = generate_farpost_api_file(
            products, file_format=file_format, request=request
        )
        
        # Получаем пароль
        password = api_settings.get_decrypted_password()
        
        # Создаем хеш sha512 от логина и пароля
        auth_string = f'{api_settings.login}:{password}'
        auth_hash = hashlib.sha512(auth_string.encode('utf-8')).hexdigest()
        
        # Подготавливаем данные для отправки
        files = {
            'data': (filename, file_content, content_type)
        }
        
        data = {
            'packetId': api_settings.packet_id,
            'auth': auth_hash
        }
        
        # Отправляем запрос
        api_url = 'https://www.farpost.ru/good/packet/api/sync'
        
        # Увеличиваем таймаут для больших файлов (примерно 1 секунда на 100 товаров, минимум 60)
        products_count = len(products) if hasattr(products, '__len__') else products.count() if hasattr(products, 'count') else 1000
        timeout = max(60, int(products_count / 100) + 30)  # Минимум 60 секунд, +30 сек на каждые 100 товаров
        
        response = requests.post(
            api_url,
            data=data,
            files=files,
            timeout=timeout
        )
        
        # Обновляем настройки
        api_settings.last_sync = timezone.now()
        
        if response.status_code == 200:
            api_settings.last_sync_status = 'success'
            api_settings.last_sync_error = ''
            api_settings.save()
            
            return True, 'Товары успешно синхронизированы с Farpost', {
                'status_code': response.status_code,
                'response_text': response.text[:500]  # Первые 500 символов
            }
        else:
            error_msg = f'Ошибка API Farpost: {response.status_code}'
            try:
                error_text = response.text[:500]
                error_msg += f' - {error_text}'
            except:
                pass
            
            api_settings.last_sync_status = 'error'
            api_settings.last_sync_error = error_msg
            api_settings.save()
            
            return False, error_msg, {
                'status_code': response.status_code,
                'response_text': response.text[:1000] if hasattr(response, 'text') else ''
            }
    
    except requests.exceptions.RequestException as e:
        error_msg = f'Ошибка при отправке запроса к API Farpost: {str(e)}'
        api_settings.last_sync = timezone.now()
        api_settings.last_sync_status = 'error'
        api_settings.last_sync_error = error_msg
        api_settings.save()
        
        return False, error_msg, {'error': str(e)}
    
    except Exception as e:
        error_msg = f'Неожиданная ошибка: {str(e)}'
        api_settings.last_sync = timezone.now()
        api_settings.last_sync_status = 'error'
        api_settings.last_sync_error = error_msg
        api_settings.save()
        
        return False, error_msg, {'error': str(e)}

