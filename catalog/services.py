"""
Сервисы автоматизации для каталога товаров.
"""
import re
import os
from django.core.files.base import ContentFile
from django.db import transaction
from .models import Category, Product, ProductImage, Brand


# =============================================================================
# 4 ОСНОВНЫЕ КАТЕГОРИИ И КЛЮЧЕВЫЕ СЛОВА ДЛЯ АВТОРАСПРЕДЕЛЕНИЯ
# =============================================================================
MAIN_CATEGORIES = {
    'Автоэлектрика': [
        'стартер', 'генератор', 'датчик', 'реле', 'проводка', 'блок управления',
        'катушка зажигания', 'катушка', 'свеча', 'свеча накала', 'свеча зажигания',
        'свечи накала', 'свечи зажигания', 'свечи', 'spark plug', 'glow plug',
        'sparkplug', 'glowplug', 'spark', 'glow',
        'аккумулятор', 'предохранитель', 'лампа',
        'фара', 'фонарь', 'сигнал', 'электро', 'sensor', 'starter', 'generator',
        'alternator', 'coil', 'ignition', 'высоковольтн', 'провод',
    ],
    'Двигатель и выхлопная система': [
        'двигатель', 'мотор', 'поршень', 'кольца поршневые', 'коленвал', 'распредвал',
        'клапан', 'прокладка гбц', 'гбц', 'блок цилиндров', 'турбина', 'турбокомпрессор',
        'форсунка', 'тнвд', 'насос топливный', 'фильтр', 'фильтры', 'масляный насос', 'помпа',
        'водяной насос', 'термостат', 'термостаты', 'радиатор', 'вентилятор', 'вискомуфта',
        'ремень грм', 'цепь грм', 'натяжитель', 'ролик', 'выхлоп', 'глушитель',
        'катализатор', 'коллектор', 'engine', 'piston', 'valve', 'turbo', 'injector',
        'вкладыш', 'шатун', 'маслосъемн', 'сальник', 'маслоохладитель',
        'интеркулер', 'egr', 'дроссель', 'впуск', 'плунжер', 'трубк', 'обратк',
        'трубка обратки', 'трубки обратки', 'обратка', 'обратки',
        'топливн', 'ремкомплект грм', 'ремкомплект двигателя', 'отопител',
        'автономн', 'печк', 'прокладка', 'ремень', 'oil seal',
        'thermostat', 'filter', 'fuel filter', 'oil filter', 'air filter',
    ],
    'Детали подвески': [
        'амортизатор', 'пружина', 'рычаг', 'сайлентблок', 'шаровая', 'опора',
        'стойка', 'втулка стабилизатора', 'стабилизатор', 'подшипник ступицы',
        'ступица', 'кулак', 'цапфа', 'тяга', 'наконечник', 'пыльник', 'отбойник',
        'suspension', 'shock', 'spring', 'arm', 'bushing', 'bearing', 'hub',
        'подвеск',
    ],
    'Трансмиссия и тормозная система': [
        'кпп', 'коробка передач', 'акпп', 'мкпп', 'сцепление', 'корзина сцепления',
        'диск сцепления', 'выжимной', 'маховик', 'редуктор', 'дифференциал',
        'полуось', 'шрус', 'кардан', 'крестовина', 'раздатка', 'раздаточная',
        'тормоз', 'колодки', 'диск тормозной', 'суппорт', 'цилиндр тормозной',
        'шланг тормозной', 'abs', 'transmission', 'clutch', 'brake', 'gearbox',
        'трансмисс', 'привод',
    ],
}

# Маппинг ключевых слов на подкатегории (внутри основных категорий)
SUBCATEGORY_KEYWORDS = {
    # Автоэлектрика
    'стартер': ('Автоэлектрика', 'Стартеры'),
    'генератор': ('Автоэлектрика', 'Генераторы'),
    'датчик': ('Автоэлектрика', 'Датчики'),
    'реле': ('Автоэлектрика', 'Реле'),
    'высоковольтн': ('Автоэлектрика', 'Высоковольтные провода'),
    'свеча накала': ('Автоэлектрика', 'Свечи накала'),
    'свечи накала': ('Автоэлектрика', 'Свечи накала'),
    'свеча зажигания': ('Автоэлектрика', 'Свечи зажигания'),
    'свечи зажигания': ('Автоэлектрика', 'Свечи зажигания'),
    'свеча': ('Автоэлектрика', 'Свечи зажигания'),  # По умолчанию свечи зажигания
    'spark plug': ('Автоэлектрика', 'Свечи зажигания'),
    'glow plug': ('Автоэлектрика', 'Свечи накала'),
    'катушка зажигания': ('Автоэлектрика', 'Катушки зажигания'),
    'катушка': ('Автоэлектрика', 'Катушки зажигания'),
    
    # Двигатель и выхлопная система  
    'турбина': ('Двигатель и выхлопная система', 'Турбины'),
    'турбокомпрессор': ('Двигатель и выхлопная система', 'Турбины'),
    'форсунка': ('Двигатель и выхлопная система', 'Форсунки'),
    'тнвд': ('Двигатель и выхлопная система', 'ТНВД'),
    'насос топливный': ('Двигатель и выхлопная система', 'Топливные насосы'),
    'топливный насос': ('Двигатель и выхлопная система', 'Топливные насосы'),
    'фильтр': ('Двигатель и выхлопная система', 'Фильтры'),
    'фильтры': ('Двигатель и выхлопная система', 'Фильтры'),
    'термостат': ('Двигатель и выхлопная система', 'Термостаты'),
    'термостаты': ('Двигатель и выхлопная система', 'Термостаты'),
    'трубк': ('Двигатель и выхлопная система', 'Трубки обратки'),
    'обратк': ('Двигатель и выхлопная система', 'Трубки обратки'),
    'трубка обратки': ('Двигатель и выхлопная система', 'Трубки обратки'),
    'трубки обратки': ('Двигатель и выхлопная система', 'Трубки обратки'),
    'радиатор': ('Двигатель и выхлопная система', 'Радиаторы'),
    'термостат': ('Двигатель и выхлопная система', 'Термостаты'),
    'помпа': ('Двигатель и выхлопная система', 'Водяные помпы'),
    'водяной насос': ('Двигатель и выхлопная система', 'Водяные помпы'),
    'вентилятор': ('Двигатель и выхлопная система', 'Вентиляторы'),
    'вискомуфта': ('Двигатель и выхлопная система', 'Вискомуфты'),
    'коленвал': ('Двигатель и выхлопная система', 'Коленвалы'),
    'распредвал': ('Двигатель и выхлопная система', 'Распредвалы'),
    'клапан': ('Двигатель и выхлопная система', 'Клапаны'),
    'поршень': ('Двигатель и выхлопная система', 'Поршни'),
    'кольца поршневые': ('Двигатель и выхлопная система', 'Кольца поршневые'),
    'вкладыш': ('Двигатель и выхлопная система', 'Вкладыши'),
    'гбц': ('Двигатель и выхлопная система', 'ГБЦ'),
    'прокладка гбц': ('Двигатель и выхлопная система', 'ГБЦ'),
    'масляный насос': ('Двигатель и выхлопная система', 'Масляные насосы'),
    'ремкомплект грм': ('Двигатель и выхлопная система', 'Ремкомплекты ГРМ'),
    'ремкомплект двигателя': ('Двигатель и выхлопная система', 'Ремкомплекты двигателя'),
    'плунжер': ('Двигатель и выхлопная система', 'Плунжерные пары'),
    'трубк': ('Двигатель и выхлопная система', 'Трубки обратки'),
    'обратк': ('Двигатель и выхлопная система', 'Трубки обратки'),
    'отопител': ('Двигатель и выхлопная система', 'Автономные отопители'),
    'автономн': ('Двигатель и выхлопная система', 'Автономные отопители'),
    'опора двигателя': ('Двигатель и выхлопная система', 'Опора двигателя'),
    'подушка двигателя': ('Двигатель и выхлопная система', 'Опора двигателя'),
    'сальник': ('Двигатель и выхлопная система', 'Сальники'),
    'прокладка': ('Двигатель и выхлопная система', 'Прокладки'),
    'ремень': ('Двигатель и выхлопная система', 'Ремни'),
    
    # Детали подвески
    'амортизатор': ('Детали подвески', 'Амортизаторы'),
    'пружина': ('Детали подвески', 'Пружины'),
    'рычаг': ('Детали подвески', 'Рычаги'),
    'сайлентблок': ('Детали подвески', 'Сайлентблоки'),
    'шаровая': ('Детали подвески', 'Шаровые опоры'),
    'подшипник ступицы': ('Детали подвески', 'Подшипники ступицы'),
    'ступица': ('Детали подвески', 'Ступицы'),
    'стойка': ('Детали подвески', 'Стойки'),
    'тяга': ('Детали подвески', 'Тяги'),
    'наконечник': ('Детали подвески', 'Наконечники'),
    
    # Трансмиссия и тормозная система
    'кпп': ('Трансмиссия и тормозная система', 'КПП'),
    'коробка передач': ('Трансмиссия и тормозная система', 'КПП'),
    'сцепление': ('Трансмиссия и тормозная система', 'Сцепление'),
    'корзина сцепления': ('Трансмиссия и тормозная система', 'Сцепление'),
    'диск сцепления': ('Трансмиссия и тормозная система', 'Сцепление'),
    'редуктор': ('Трансмиссия и тормозная система', 'Редукторы'),
    'полуось': ('Трансмиссия и тормозная система', 'Полуоси'),
    'шрус': ('Трансмиссия и тормозная система', 'ШРУСы'),
    'кардан': ('Трансмиссия и тормозная система', 'Карданы'),
    'крестовина': ('Трансмиссия и тормозная система', 'Крестовины'),
    'тормоз': ('Трансмиссия и тормозная система', 'Тормозные колодки'),
    'колодки': ('Трансмиссия и тормозная система', 'Тормозные колодки'),
    'диск тормозной': ('Трансмиссия и тормозная система', 'Тормозные диски'),
    'суппорт': ('Трансмиссия и тормозная система', 'Суппорты'),
}

# Базовые бренды (используются если БД недоступна)
_DEFAULT_BRANDS = [
    # Японские автопроизводители
    'Toyota', 'Isuzu', 'Hino', 'Mitsubishi', 'Nissan', 'Mazda', 'Honda', 'Suzuki',
    'Daihatsu', 'Subaru', 'Lexus', 'Infiniti', 'Acura',
    # Корейские автопроизводители
    'Hyundai', 'Kia', 'Daewoo', 'Ssangyong', 'Genesis',
    # Европейские автопроизводители
    'Volvo', 'Scania', 'MAN', 'Mercedes', 'BMW', 'Audi', 'Volkswagen',
    'DAF', 'Iveco', 'Renault', 'Peugeot', 'Citroen', 'Opel',
    # Американские автопроизводители
    'Ford', 'Chevrolet', 'Cadillac', 'Jeep', 'Dodge', 'Chrysler',
    # Китайские автопроизводители
    'Chery', 'Geely', 'Haval', 'Great Wall', 'BYD', 'Lifan', 'Changan',
    # Производители запчастей - электрика
    'Bosch', 'Denso', 'Aisin', 'NGK', 'HKT', 'Valeo', 'Hitachi', 'Delco',
    # Производители запчастей - подвеска/трансмиссия
    'KYB', 'Monroe', 'Sachs', 'LUK', 'INA', 'SKF', 'NTN', 'Koyo', 'NSK',
    'Mobis', 'Mando', 'CTR', 'GMB', 'FEBEST', 'ASAKASHI', 'MASUMA', 'GKN',
    'TOYO', 'GUT', 'Kayaba', 'Tokico',
    # Производители запчастей - двигатель/фильтры
    'NPR', 'Mahle', 'Knecht', 'Mann', 'Filtron', 'Nipparts', 'Japan Parts',
    'Teikin', 'TP', 'Riken', 'Hastings',
    # Производители запчастей - сальники/прокладки/ремни
    'NOK', 'Corteco', 'Elring', 'Victor Reinz', 'Goetze', 'Payen',
    'Gates', 'Dayco', 'Continental', 'Bando', 'Mitsuboshi',
    # Производители запчастей - тормоза
    'Akebono', 'Advics', 'Nisshinbo', 'Sumitomo', 'TRW', 'ATE', 'Brembo',
    # Производители запчастей - турбины
    'Garrett', 'IHI', 'MHI', 'Holset', 'BorgWarner',
    # Прочие бренды
    'ACDelco', 'Motorcraft', 'Mopar', 'OE', 'Genuine',
]

# Кэш для брендов из БД
_brands_cache = None
_brands_cache_time = None

def get_known_brands():
    """
    Получает список известных брендов из базы данных.
    Кэширует результат на 5 минут.
    Если справочник пуст — использует базовые бренды.
    """
    global _brands_cache, _brands_cache_time
    import time
    
    current_time = time.time()
    
    # Если кэш действителен (менее 5 минут), возвращаем его
    if _brands_cache is not None and _brands_cache_time is not None:
        if current_time - _brands_cache_time < 300:  # 5 минут
            return _brands_cache
    
    try:
        from catalog.models import Brand
        # Получаем активные бренды из БД
        db_brands = list(Brand.objects.filter(is_active=True).values_list('name', flat=True))
        
        # Если справочник не пуст — используем только его
        if db_brands:
            _brands_cache = db_brands
        else:
            # Если справочник пуст — используем базовые (для автоопределения при импорте)
            _brands_cache = _DEFAULT_BRANDS
        
        _brands_cache_time = current_time
        return _brands_cache
    except Exception:
        # Если БД недоступна, используем базовые
        return _DEFAULT_BRANDS

def clear_brands_cache():
    """Очищает кэш брендов (вызывать после изменений в админке)."""
    global _brands_cache, _brands_cache_time
    _brands_cache = None
    _brands_cache_time = None

# Для обратной совместимости
KNOWN_BRANDS = _DEFAULT_BRANDS


def detect_category(text):
    """
    Автоматически определяет категорию по ключевым словам.
    
    1. Сначала ищет в категориях из базы данных (по полю keywords)
    2. Если не найдено, использует жёстко заданные MAIN_CATEGORIES
    3. По умолчанию возвращает 'Двигатель и выхлопная система'
    """
    text_lower = text.lower()
    
    # 1. Сначала проверяем категории из базы данных (корневые с ключевыми словами)
    try:
        from .models import Category
        # Получаем корневые категории с заполненными ключевыми словами
        db_categories = Category.objects.filter(
            parent__isnull=True,
            is_active=True,
            keywords__isnull=False
        ).exclude(keywords='')
        
        for category in db_categories:
            for keyword in category.get_keywords_list():
                if keyword in text_lower:
                    return category.name
    except Exception:
        # Если база данных недоступна, используем hardcoded
        pass
    
    # 2. Если не нашли в БД, используем hardcoded категории
    for category_name, keywords in MAIN_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return category_name
    
    # По умолчанию - Двигатель и выхлопная система
    return 'Двигатель и выхлопная система'


def detect_subcategory_info(text):
    """
    Определяет подкатегорию по ключевым словам.
    Возвращает кортеж (основная_категория, подкатегория) или None.
    """
    text_lower = text.lower()
    
    for keyword, (main_cat, subcat) in SUBCATEGORY_KEYWORDS.items():
        if keyword.lower() in text_lower:
            return (main_cat, subcat)
    
    return None


def detect_brand(text):
    """
    Автоматически определяет бренд по тексту.
    Использует бренды из базы данных.
    
    Важно: TOYO и TOYOTA - это разные бренды!
    Проверяет более длинные совпадения первыми, чтобы если в тексте есть "TOYOTA",
    то находился именно "TOYOTA", а не "TOYO".
    Но если в тексте только "TOYO", то находится именно "TOYO".
    """
    text_upper = text.upper()
    known_brands = get_known_brands()
    
    # Сортируем бренды по длине в убывающем порядке, чтобы более длинные совпадения проверялись первыми
    # Это важно для случаев, когда один бренд является частью другого (например, TOYO и TOYOTA)
    sorted_brands = sorted(known_brands, key=lambda x: len(x), reverse=True)
    
    for brand in sorted_brands:
        brand_upper = brand.upper()
        # Используем более точную проверку: бренд должен быть отдельным словом
        # Учитываем различные разделители: пробелы, запятые, начало/конец строки
        # Паттерн: начало строки ИЛИ не буква/цифра, затем бренд, затем не буква/цифра ИЛИ конец строки
        # Это гарантирует, что "TOYO" не будет найден в "TOYOTA", и наоборот
        pattern = r'(?:^|[^A-Z0-9])' + re.escape(brand_upper) + r'(?:[^A-Z0-9]|$)'
        if re.search(pattern, text_upper):
            return brand
    
    return None


def extract_article(text):
    """
    Извлекает артикул из текста.
    Артикул обычно содержит буквы и цифры, например: 23300-78090, ME220745, 1-13200-469-0
    Для крестовин TOYO формат: TT-124, TU-1210, GUT-25
    """
    # Паттерны для артикулов (в порядке приоритета)
    patterns = [
        # TOYO/GUT style: TT-124, TU-1210, GUT-25, GU-1210 (2-3 буквы + дефис + 1-4 цифры)
        r'\b([A-Z]{2,3}-\d{1,4})\b',
        r'\b(\d{5}-\d{5})\b',  # Toyota style: 23300-78090
        r'\b([A-Z]{2}\d{6})\b',  # Mitsubishi style: ME220745
        r'\b(\d-\d{5}-\d{3}-\d)\b',  # Isuzu style: 1-13200-469-0
        r'\b(\d{6})\b',  # 6-digit codes: 332120, 331008
        r'\b([A-Z0-9\-]{6,20})\b',  # Generic alphanumeric with dashes
    ]
    
    known_brands = get_known_brands()
    known_brands_upper = [b.upper() for b in known_brands]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).upper()
            # Исключаем известные бренды
            if candidate not in known_brands_upper:
                return candidate
    
    return None


def parse_product_name(name):
    """
    Парсит название товара и извлекает данные.
    Возвращает словарь с полями: brand, article, category, clean_name, oem_number, applicability, characteristics
    
    Поддерживает 4 типа номенклатуры:
    1. Наименование и размер: "Газлифт 20*450"
       - Извлекает: размер (20*450) → characteristics
    2. Характеристика с одним OEM: "Клапан VVTI TOYOTA 15330-20010 1MZFE"
       - Извлекает: бренд (TOYOTA), OEM (15330-20010) → article и cross_numbers, применимость (1MZFE)
    3. Характеристика с фирменным артикулом и OEM: "Диск сцепления TOYOTA TYD150U 31250-25160 1KDFTV 260*170*10*29"
       - Извлекает: бренд (TOYOTA), артикул (TYD150U) → article, OEM (31250-25160) → cross_numbers, 
         применимость (1KDFTV), размер (260*170*10*29) → characteristics
    4. Характеристика с двумя фирменными артикулами и OEM: "Свеча зажигания DENSO IK16#4(5303#4)/BKR5EIX-11(5464) 90919-01209 1GFE IRIDIUM"
       - Извлекает: бренд (DENSO), артикулы (IK16#4(5303#4)/BKR5EIX-11(5464)) → article, 
         OEM (90919-01209) → cross_numbers, применимость (1GFE), материал (IRIDIUM) → characteristics
    """
    result = {
        'brand': None,
        'article': None,
        'category': None,
        'clean_name': name,
        'oem_number': None,
        'applicability': None,
        'characteristics': None,
    }
    
    # Определяем категорию
    result['category'] = detect_category(name)
    
    # Определяем бренд
    result['brand'] = detect_brand(name)
    
    # Ищем OEM номер в разных форматах
    # Форматы OEM: 15330-20010, 31250-25160, 90919-01209, 48510-B1020, 51601-S5P-G03
    # Паттерн: 5 цифр + дефис + 5 цифр/букв (Toyota/Nissan/Honda стиль)
    # Или: 5 цифр + дефис + буквы + цифры (Nissan стиль: 22620-AA000)
    
    # Сначала ищем стандартный формат OEM: 5 цифр-5 цифр или 5 цифр-буквы-цифры
    oem_patterns = [
        r'\b(\d{5}-\d{5})\b',  # Toyota/Honda: 15330-20010, 31250-25160, 90919-01209
        r'\b(\d{5}-[A-Z]{1,2}\d{3}[A-Z]?)\b',  # Nissan: 22620-AA000, 16546-ED00A
        r'\b(\d{5}-[A-Z0-9]{3,6})\b',  # Общий формат: 48510-B1020, 51601-S5P-G03
    ]
    
    for pattern in oem_patterns:
        oem_matches = re.findall(pattern, name)
        if oem_matches:
            # Берем последний найденный OEM (обычно он идет после артикулов)
            oem_candidate = oem_matches[-1]
            # Проверяем, что это не часть артикула или другого кода
            # OEM обычно не содержит специальных символов кроме дефиса
            if re.match(r'^\d{5}-[A-Z0-9\-]{3,10}$', oem_candidate, re.IGNORECASE):
                result['oem_number'] = oem_candidate.upper()
                break
    
    # Если не нашли через паттерны, пробуем найти после слеша (старый формат)
    if not result['oem_number']:
        slash_positions = [i for i, char in enumerate(name) if char == '/']
        if slash_positions:
            # Берем последний слеш
            last_slash_pos = slash_positions[-1]
            after_last_slash = name[last_slash_pos + 1:].strip()
            
            # Ищем OEM номер как единое целое (до первого пробела)
            oem_match = re.match(r'^([A-Z0-9\-]{3,20})(?:\s|$)', after_last_slash)
            if oem_match:
                oem_candidate = oem_match.group(1)
                if len(oem_candidate) <= 20 and ' ' not in oem_candidate:
                    engine_pattern = re.compile(r'^\d?[A-Z]{2,4}-?F[E|D]$', re.IGNORECASE)
                    if not engine_pattern.match(oem_candidate):
                        result['oem_number'] = oem_candidate
    
    # Извлекаем фирменный артикул производителя
    # ЛОГИКА для 4 типов номенклатуры:
    # Тип 1: "Газлифт 20*450" - артикула нет
    # Тип 2: "Клапан VVTI TOYOTA 15330-20010 1MZFE" - артикула нет, только OEM
    # Тип 3: "Диск сцепления TOYOTA TYD150U 31250-25160" - фирменный артикул TYD150U
    # Тип 4: "Свеча зажигания DENSO IK16#4(5303#4)/BKR5EIX-11(5464) 90919-01209" - два артикула через слеш
    
    if result['brand']:
        brand_upper = result['brand'].upper()
        brand_escaped = re.escape(result['brand'])
        
        # Ищем фирменный артикул после бренда, перед OEM номером
        # Формат: БРЕНД [АРТИКУЛ] OEM
        if result.get('oem_number'):
            # Если есть OEM, ищем артикул между брендом и OEM
            brand_pos = name.upper().find(brand_upper)
            if brand_pos != -1:
                after_brand = name[brand_pos + len(result['brand']):].strip()
                # Ищем позицию OEM номера
                oem_pos = after_brand.upper().find(result['oem_number'].upper())
                if oem_pos > 0:
                    # Между брендом и OEM должен быть артикул
                    article_part = after_brand[:oem_pos].strip()
                    
                    # Паттерны для фирменных артикулов (в порядке приоритета)
                    article_patterns = [
                        # Тип 4: Два артикула через слеш с скобками: IK16#4(5303#4)/BKR5EIX-11(5464)
                        r'\b([A-Z0-9#\-]+(?:\([A-Z0-9#\-]+\))?/[A-Z0-9#\-]+(?:\([A-Z0-9#\-]+\))?)\b',
                        # Тип 4: Два артикула через слеш без скобок: IK16#4/BKR5EIX-11
                        r'\b([A-Z0-9#\-]+/[A-Z0-9#\-]+)\b',
                        # Тип 3: Артикул с скобками: IK16#4(5303#4)
                        r'\b([A-Z]{2,8}\d{0,4}[A-Z0-9#\-]*\([A-Z0-9#\-]+\))\b',
                        # Тип 3: Простой артикул: TYD150U, IK16#4, BKR5EIX-11
                        r'\b([A-Z]{2,8}\d{0,4}[A-Z0-9#\-]{0,10})\b',
                    ]
                    
                    for pattern in article_patterns:
                        article_match = re.search(pattern, article_part, re.IGNORECASE)
                        if article_match:
                            candidate = article_match.group(1).strip()
                            # Проверяем, что это не OEM номер (OEM обычно 5 цифр-5 цифр)
                            if not re.match(r'^\d{5}-\d{5}$', candidate):
                                # Проверяем, что это не код двигателя
                                if not re.match(r'^\d?[A-Z]{2,4}-?F[E|D]$', candidate, re.IGNORECASE):
                                    result['article'] = candidate.upper()
                                    break
        
        # Если не нашли через OEM, ищем стандартные форматы
        if not result['article']:
            # Для TOYO, GMB, FEBEST и подобных - ищем артикул типа TT-124, TU-1210, GUT-25
            if brand_upper in ['TOYO', 'GMB', 'FEBEST', 'ASAKASHI', 'MASUMA', 'GUT', 'GKN']:
                toyo_article_match = re.search(rf'\b{brand_escaped}\s+([A-Z]{{2,3}}-\d{{1,4}})\b', name, re.IGNORECASE)
                if toyo_article_match:
                    result['article'] = toyo_article_match.group(1).upper()
            
            # Ищем формат: бренд + пробел + артикул (буквы+цифры, может быть с дефисом, #, скобками)
            if not result['article']:
                # Паттерн: бренд + пробел + артикул (2-30 символов: буквы, цифры, дефисы, #, скобки, слеши)
                brand_article_match = re.search(rf'\b{brand_escaped}\s+([A-Z0-9#\-\(\)/]{{2,30}})\b', name, re.IGNORECASE)
                if brand_article_match:
                    candidate = brand_article_match.group(1).strip()
                    # Проверяем, что это не OEM номер (5 цифр-5 цифр)
                    if not re.match(r'^\d{5}-\d{5}$', candidate):
                        # Проверяем, что это не код двигателя
                        if not re.match(r'^\d?[A-Z]{2,4}-?F[E|D]$', candidate, re.IGNORECASE):
                            # Проверяем, что это похоже на артикул (содержит буквы)
                            if re.search(r'[A-Z]', candidate, re.IGNORECASE):
                                result['article'] = candidate.upper()
    
    # Если не нашли фирменный артикул, используем OEM как артикул (код детали)
    # Это для типов 1 и 2, где нет фирменного артикула
    if not result['article'] and result.get('oem_number'):
        result['article'] = result['oem_number']
    
    # Если все еще не нашли, пробуем стандартные методы
    if not result['article']:
        # Ищем 6-значные числа
        article_matches = re.findall(r'\b(\d{6})\b', name)
        if article_matches:
            for match in reversed(article_matches):
                if match not in ['202512', '202518', '202425']:
                    result['article'] = match
                    break
        
        # Последняя попытка - стандартный метод
        if not result['article']:
            result['article'] = extract_article(name)
    
    # Извлекаем применимость (коды двигателей, модели и т.д.)
    # Паттерн для кодов двигателей: 1MZFE, 1KDFTV, 1GFE, 1ZRFE, 2ZRFE, 1NZ-FE, 4M40, LD20, RD28 и т.д.
    engine_pattern = r'\b(\d?[A-Z]{1,3}\d?[A-Z]{0,3}-?[A-Z]{0,2}\d{0,2}[A-Z]?)\b'
    
    applicability_parts = []
    
    # Ищем коды двигателей (формат: 1MZFE, 1KDFTV, 1GFE и т.д.)
    # Обычно они идут после OEM номера или в конце названия
    engine_matches = re.findall(r'\b(\d[A-Z]{2,5}[A-Z]?)\b', name, re.IGNORECASE)
    for eng in engine_matches:
        eng_upper = eng.upper()
        # Проверяем, что это не часть артикула или OEM номера
        if (eng_upper not in (result.get('article') or '').upper() and 
            eng_upper not in (result.get('oem_number') or '').upper() and
            len(eng_upper) >= 3 and len(eng_upper) <= 8):
            # Проверяем, что это похоже на код двигателя (содержит и буквы, и цифры)
            if re.search(r'[A-Z]', eng_upper) and re.search(r'\d', eng_upper):
                applicability_parts.append(eng_upper)
    
    # Ищем связки через слеш типа "1ZRFE/2ZRFE" или "LD20/RD28"
    # Но исключаем артикулы типа "IK16#4(5303#4)/BKR5EIX-11(5464)"
    slash_groups = re.findall(r'([A-Z0-9#\-]+(?:/[A-Z0-9#\-]+)+)', name)
    
    for group in slash_groups:
        # Проверяем, что это не артикул (артикулы обычно содержат #, скобки или длинные)
        # Артикулы типа IK16#4(5303#4)/BKR5EIX-11(5464) содержат # или скобки
        if '#' in group or '(' in group:
            continue
        # Проверяем, что это не артикул (артикулы обычно содержат 5+ цифр подряд)
        if not re.search(r'\d{5,}', group):
            parts = group.split('/')
            # Проверяем, похоже ли это на коды двигателей/кузовов
            is_applicability = all(
                re.match(r'^[A-Z0-9\-]{2,8}$', p, re.IGNORECASE) 
                for p in parts
            )
            if is_applicability and len(parts) >= 2:
                applicability_parts.extend([p.upper() for p in parts])
    
    # Убираем дубликаты, сохраняя порядок
    if applicability_parts:
        seen = set()
        unique_parts = []
        for p in applicability_parts:
            p_upper = p.upper()
            if p_upper not in seen:
                seen.add(p_upper)
                unique_parts.append(p)
        if unique_parts:
            result['applicability'] = ', '.join(unique_parts)
    
    # Извлекаем характеристики (размеры, вольтаж, материал и т.д.)
    # Характеристики обычно идут в конце названия, после применимости
    characteristics_parts = []
    name_upper = name.upper()  # Используем для поиска, не изменяем исходную строку
    
    # Ищем размеры (формат: 20*450, 260*170*10*29, 20x450)
    # Паттерн: числа через * или x
    size_pattern = r'\b(\d+(?:\*|x)\d+(?:(?:\*|x)\d+)*)\b'
    size_matches = re.findall(size_pattern, name)
    for size in size_matches:
        # Проверяем, что это не часть артикула или OEM
        size_upper = size.upper()
        if (size_upper not in (result.get('article') or '').upper() and
            size_upper not in (result.get('oem_number') or '').upper()):
            characteristics_parts.append(f"Размер: {size}")
    
    # Ищем вольтаж (формат: 12V, 24V, 12V-11V)
    voltage_patterns = [
        r'\b(\d+V(?:-\d+V)?)\b',  # 12V, 24V, 12V-11V
        r'\b(\d+\s*V(?:-\d+\s*V)?)\b',  # 12 V, 24 V (с пробелом)
    ]
    for pattern in voltage_patterns:
        voltage_matches = re.findall(pattern, name, re.IGNORECASE)
        for voltage in voltage_matches:
            voltage_clean = voltage.upper().replace(' ', '')
            # Проверяем, что это не часть артикула или OEM
            if (voltage_clean not in (result.get('article') or '').upper() and
                voltage_clean not in (result.get('oem_number') or '').upper()):
                # Проверяем, что еще не добавлено
                if not any('Напряжение:' in p and voltage_clean in p for p in characteristics_parts):
                    characteristics_parts.append(f"Напряжение: {voltage_clean}")
    
    # Ищем материал (IRIDIUM, PLATINUM, COPPER и т.д.)
    material_keywords = [
        'IRIDIUM', 'ИРИДИЙ', 'ИРИДИЕВЫЙ',
        'PLATINUM', 'ПЛАТИНА', 'ПЛАТИНОВЫЙ',
        'COPPER', 'МЕДЬ', 'МЕДНЫЙ',
        'NICKEL', 'НИКЕЛЬ', 'НИКЕЛЕВЫЙ',
        'SILVER', 'СЕРЕБРО', 'СЕРЕБРЯНЫЙ',
    ]
    for keyword in material_keywords:
        # Ищем ключевое слово как отдельное слово
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, name_upper):
            # Проверяем, что это не часть артикула или бренда
            keyword_upper = keyword.upper()
            if (keyword_upper not in (result.get('article') or '').upper() and
                keyword_upper not in (result.get('brand') or '').upper()):
                # Определяем русское название
                material_map = {
                    'IRIDIUM': 'Иридий',
                    'ИРИДИЙ': 'Иридий',
                    'ИРИДИЕВЫЙ': 'Иридий',
                    'PLATINUM': 'Платина',
                    'ПЛАТИНА': 'Платина',
                    'ПЛАТИНОВЫЙ': 'Платина',
                    'COPPER': 'Медь',
                    'МЕДЬ': 'Медь',
                    'МЕДНЫЙ': 'Медь',
                    'NICKEL': 'Никель',
                    'НИКЕЛЬ': 'Никель',
                    'НИКЕЛЕВЫЙ': 'Никель',
                    'SILVER': 'Серебро',
                    'СЕРЕБРО': 'Серебро',
                    'СЕРЕБРЯНЫЙ': 'Серебро',
                }
                material_name = material_map.get(keyword_upper, keyword_upper)
                # Проверяем, что еще не добавлено
                if not any('Материал:' in p and material_name in p for p in characteristics_parts):
                    characteristics_parts.append(f"Материал: {material_name}")
                break
    
    # Ищем другие характеристики в конце названия
    # После применимости и OEM могут быть дополнительные характеристики
    # Определяем позицию последнего значимого элемента (OEM или применимость)
    last_element_pos = -1
    if result.get('oem_number'):
        oem_pos = name_upper.rfind(result['oem_number'].upper())
        if oem_pos > last_element_pos:
            last_element_pos = oem_pos + len(result['oem_number'])
    
    if result.get('applicability'):
        applicability_pos = name_upper.rfind(result['applicability'].upper())
        if applicability_pos > last_element_pos:
            last_element_pos = applicability_pos + len(result['applicability'])
    
    # Берем текст после последнего элемента
    if last_element_pos > 0:
        after_last = name[last_element_pos:].strip()
        # Убираем уже найденные характеристики из строки для поиска
        search_text = after_last
        for char_part in characteristics_parts:
            if ':' in char_part:
                char_value = char_part.split(':', 1)[1].strip()
                search_text = search_text.replace(char_value, '', 1)
        
        # Ищем оставшиеся слова (длина 3-20 символов, только буквы)
        remaining_words = re.findall(r'\b([A-ZА-Я]{3,20})\b', search_text, re.IGNORECASE)
        for word in remaining_words:
            word_upper = word.upper()
            # Пропускаем, если это часть артикула, OEM, применимости или известные материалы
            if (word_upper not in (result.get('article') or '').upper() and
                word_upper not in (result.get('oem_number') or '').upper() and
                word_upper not in (result.get('applicability') or '').upper() and
                word_upper not in material_keywords and
                len(word_upper) >= 3):
                # Это может быть дополнительная характеристика
                # Добавляем только если это не код двигателя
                if not re.match(r'^\d[A-Z]{2,5}$', word_upper):
                    # Проверяем, что еще не добавлено
                    if not any('Характеристика:' in p and word_upper in p.upper() for p in characteristics_parts):
                        characteristics_parts.append(f"Характеристика: {word}")
    
    # Формируем строку характеристик
    if characteristics_parts:
        result['characteristics'] = '\n'.join(characteristics_parts)
    
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
    Получает одну из 4 основных категорий по названию.
    НЕ СОЗДАЕТ новые корневые категории!
    Для подкатегорий - создает если нужно.
    """
    if not category_name:
        return None
    
    category_name_clean = category_name.strip()
    
    if parent:
        # Для подкатегорий - ищем или создаем
        existing = Category.objects.filter(
            name__iexact=category_name_clean,
            parent=parent
        ).first()
        
        if existing:
            return existing
        
        # Создаем подкатегорию
        return Category.objects.create(
            name=category_name_clean,
            parent=parent,
            is_active=True
        )
    else:
        # Для корневых - ТОЛЬКО ищем среди 4 основных, НЕ создаем!
        existing = Category.objects.filter(
            name__iexact=category_name_clean,
            parent=None
        ).first()
        
        if existing:
            return existing
        
        # Если не нашли точно, возвращаем "Двигатель и выхлопная система" по умолчанию
        default = Category.objects.filter(
            name='Двигатель и выхлопная система',
            parent=None
        ).first()
        
        return default


def get_category_for_product(product_name):
    """
    Определяет категорию и подкатегорию для товара по его названию.
    Возвращает объект Category (подкатегорию если найдена, иначе основную категорию).
    """
    # Сначала пытаемся определить подкатегорию
    subcat_info = detect_subcategory_info(product_name)
    
    if subcat_info:
        main_cat_name, subcat_name = subcat_info
        # Находим основную категорию
        main_category = Category.objects.filter(
            name__iexact=main_cat_name,
            parent=None
        ).first()
        
        if main_category:
            # Ищем или создаем подкатегорию
            subcategory = Category.objects.filter(
                name__iexact=subcat_name,
                parent=main_category
            ).first()
            
            if not subcategory:
                subcategory = Category.objects.create(
                    name=subcat_name,
                    parent=main_category,
                    is_active=True
                )
            
            return subcategory
    
    # Если подкатегория не определена, определяем основную категорию
    main_cat_name = detect_category(product_name)
    main_category = Category.objects.filter(
        name__iexact=main_cat_name,
        parent=None
    ).first()
    
    # Если основная категория не найдена, берем первую из 4
    if not main_category:
        main_category = Category.objects.filter(parent=None).first()
    
    return main_category


def get_or_create_subcategory(product_name, parent_category):
    """
    Получает существующую подкатегорию или создаёт новую на основе названия товара.
    Если товар "амортизатор" и категория "Подвеска", создаст подкатегорию "Амортизаторы".
    Ищет существующую подкатегорию регистронезависимо.
    """
    if not parent_category or not product_name:
        return parent_category
    
    # Определяем название подкатегории
    subcategory_name = detect_subcategory(product_name, parent_category)
    
    if not subcategory_name:
        return parent_category
    
    subcategory_name_clean = subcategory_name.strip()
    
    # Сначала ищем существующую подкатегорию (регистронезависимый поиск)
    existing = Category.objects.filter(
        name__iexact=subcategory_name_clean,
        parent=parent_category
    ).first()
    
    if existing:
        return existing
    
    # Создаём только если не нашли существующую
    subcategory = Category.objects.create(
        name=subcategory_name_clean,
        parent=parent_category,
        is_active=True
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
                
                # Определяем артикул (Артикул1 или из названия)
                article = str(row.get('article', '')).strip()
                # Если артикул не указан в отдельной колонке, пытаемся извлечь из названия
                if not article and parsed['article']:
                    article = parsed['article']
                
                # OEM номер (Артикул2) → добавляем в кросс-номера
                oem_number = str(row.get('oem_number', '')).strip()
                
                # Определяем бренд (из колонки Марка или автоопределение)
                if auto_brand:
                    brand = row.get('brand', '').strip() or parsed['brand'] or ''
                else:
                    brand = row.get('brand', '').strip()
                
                # Определяем категорию
                # Сначала пробуем из колонки category_name (Номенклатура из 1С)
                category_name = str(row.get('category_name', '')).strip()
                if category_name:
                    category = get_category_for_product(category_name)
                else:
                    category = get_category_for_product(name)
                
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
                
                # Проверяем существует ли товар ТОЛЬКО в основном каталоге
                # Приоритет: external_id > article > name
                product = None
                external_id = str(row.get('external_id', '')).strip()
                
                if external_id:
                    product = Product.objects.filter(
                        external_id=external_id,
                        catalog_type='retail'  # ТОЛЬКО основной каталог!
                    ).first()
                
                if not product and article:
                    product = Product.objects.filter(
                        article=article,
                        catalog_type='retail'  # ТОЛЬКО основной каталог!
                    ).first()
                
                if not product:
                    product = Product.objects.filter(
                        name=name,
                        catalog_type='retail'  # ТОЛЬКО основной каталог!
                    ).first()
                
                # Формируем применимость из полей: двигатель, кузов, модель
                applicability_parts = []
                if row.get('engine'):
                    applicability_parts.append(str(row['engine']).strip())
                if row.get('body'):
                    applicability_parts.append(str(row['body']).strip())
                if row.get('model'):
                    applicability_parts.append(str(row['model']).strip())
                
                # Добавляем применимость из парсинга или колонки
                if row.get('applicability'):
                    applicability_parts.append(str(row['applicability']).strip())
                elif parsed.get('applicability'):
                    applicability_parts.append(parsed['applicability'])
                
                applicability = ', '.join([p for p in applicability_parts if p])
                
                # Формируем характеристики из полей: размер, вольтаж, цвет, год и т.д.
                characteristics_parts = []
                
                # Размер - может быть вольтаж (12V-11V), материал (IRIDIUM), или габариты
                size_val = str(row.get('size', '')).strip()
                if size_val:
                    # Проверяем, это вольтаж?
                    if 'V' in size_val.upper() and any(c.isdigit() for c in size_val):
                        characteristics_parts.append(f"Напряжение: {size_val}")
                    # Проверяем, это материал?
                    elif size_val.upper() in ['IRIDIUM', 'PLATINUM', 'COPPER', 'ИРИДИЙ', 'ПЛАТИНА', 'МЕДЬ']:
                        characteristics_parts.append(f"Материал: {size_val}")
                    else:
                        characteristics_parts.append(f"Размер: {size_val}")
                
                # Позиционирование
                if row.get('side'):
                    characteristics_parts.append(f"Сторона: {row['side']}")
                if row.get('position'):
                    characteristics_parts.append(f"Позиция: {row['position']}")
                if row.get('direction'):
                    characteristics_parts.append(f"Направление: {row['direction']}")
                
                # Другие характеристики
                if row.get('year'):
                    characteristics_parts.append(f"Год: {row['year']}")
                if row.get('color'):
                    characteristics_parts.append(f"Цвет: {row['color']}")
                if row.get('note'):
                    characteristics_parts.append(f"Примечание: {row['note']}")
                
                # Добавляем существующие характеристики
                if row.get('characteristics'):
                    characteristics_parts.append(str(row['characteristics']).strip())
                
                characteristics = '\n'.join([p for p in characteristics_parts if p])
                
                # Формируем кросс-номера (OEM + существующие)
                cross_numbers_parts = []
                if oem_number:
                    cross_numbers_parts.append(oem_number)
                if row.get('cross_numbers'):
                    cross_numbers_parts.append(str(row['cross_numbers']).strip())
                cross_numbers = ', '.join([p for p in cross_numbers_parts if p])
                
                # Определяем наличие на основе остатка
                availability = row.get('availability', 'in_stock')
                if quantity_value == 0:
                    availability = 'out_of_stock'
                elif quantity_value > 0:
                    availability = 'in_stock'
                
                # Определяем состояние товара
                condition = 'new'
                if row.get('condition'):
                    cond_val = str(row['condition']).strip().lower()
                    if cond_val in ['да', 'новый', 'new', 'yes', '1', 'true']:
                        condition = 'new'
                    elif cond_val in ['нет', 'б/у', 'used', 'no', '0', 'false', 'бу']:
                        condition = 'used'
                
                if product:
                    # Обновляем существующий товар в ОСНОВНОМ каталоге
                    # Убеждаемся, что catalog_type остаётся 'retail'
                    if product.catalog_type != 'retail':
                        # Если товар был из другого каталога, создаём новый
                        product = None
                    else:
                        product.name = name
                        if article:
                            product.article = article
                        # Обновляем external_id если он есть
                        if external_id:
                            product.external_id = external_id
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
                        if cross_numbers:
                            product.cross_numbers = cross_numbers
                        if characteristics:
                            product.characteristics = characteristics
                        if row.get('farpost_url'):
                            product.farpost_url = row['farpost_url']
                        if quantity_value >= 0:
                            product.quantity = quantity_value
                        product.condition = condition
                        product.availability = availability
                        product.catalog_type = 'retail'  # Гарантируем, что остаётся в основном каталоге
                        product.save()
                        stats['updated'] += 1
                else:
                    # Создаём новый товар в ОСНОВНОМ каталоге
                    product = Product.objects.create(
                        name=name,
                        article=article,
                        external_id=external_id if external_id else None,
                        brand=brand,
                        category=category,
                        price=price_value,
                        description=row.get('description', ''),
                        short_description=row.get('short_description', ''),
                        applicability=applicability,
                        cross_numbers=cross_numbers,
                        characteristics=characteristics,
                        farpost_url=row.get('farpost_url', ''),
                        condition=condition,
                        availability=availability,
                        quantity=quantity_value,
                        catalog_type='retail',  # ОСНОВНОЙ КАТАЛОГ!
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
    
    # Пробуем найти по артикулу (точное совпадение) ТОЛЬКО в основном каталоге
    product = Product.objects.filter(
        article__iexact=name.replace(' ', '-'),
        catalog_type='retail'  # ТОЛЬКО основной каталог!
    ).first()
    if product:
        return product
    
    product = Product.objects.filter(
        article__iexact=name.replace(' ', ''),
        catalog_type='retail'  # ТОЛЬКО основной каталог!
    ).first()
    if product:
        return product
    
    # Пробуем найти по артикулу (частичное совпадение) ТОЛЬКО в основном каталоге
    article = extract_article(name)
    if article:
        product = Product.objects.filter(
            article__icontains=article,
            catalog_type='retail'  # ТОЛЬКО основной каталог!
        ).first()
        if product:
            return product
    
    # Поиск по названию ТОЛЬКО в основном каталоге
    words = name.split()
    if len(words) >= 2:
        # Ищем товары, содержащие все слова из имени файла ТОЛЬКО в основном каталоге
        products = Product.objects.filter(catalog_type='retail')  # ТОЛЬКО основной каталог!
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
            category = get_category_for_product(name)
            
            product = Product.objects.create(
                name=name,
                article=parsed['article'] or '',
                brand=parsed['brand'] or '',
                category=category,
                catalog_type='retail',  # ОСНОВНОЙ КАТАЛОГ!
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


def process_bulk_import_wholesale(data_rows, auto_category=True, auto_brand=True, update_existing=True):
    """
    Массовый импорт товаров для ПАРТНЁРСКОГО каталога.
    Товары создаются с catalog_type='wholesale' и не пересекаются с основным сайтом.
    
    data_rows: список словарей с данными товаров
    auto_category: автоматически определять категорию
    auto_brand: автоматически определять бренд
    update_existing: обновлять существующие товары
    
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
                # Получаем название товара
                name = str(row.get('name', '')).strip()
                
                if not name or name.lower() in ['none', 'null', '']:
                    stats['errors'] += 1
                    stats['error_details'].append(f'Строка {i}: пустое название товара')
                    continue
                
                # Парсим название
                parsed = parse_product_name(name)
                
                # Определяем артикул
                # ЛОГИКА: 
                # - Если есть фирменный артикул в parsed - используем его
                # - Если нет фирменного артикула, но есть OEM - используем OEM как артикул
                # - Если артикул явно указан в данных - используем его
                article = str(row.get('article', '')).strip()
                if not article and parsed['article']:
                    article = parsed['article']
                
                # Определяем OEM номер для cross_numbers
                # OEM номер сохраняем в cross_numbers, если есть фирменный артикул
                # Если нет фирменного артикула, OEM уже используется как article
                oem_number = str(row.get('oem_number', '')).strip()
                if not oem_number and parsed.get('oem_number'):
                    oem_number = parsed['oem_number']
                
                # Определяем применимость
                applicability = str(row.get('applicability', '')).strip()
                if not applicability and parsed.get('applicability'):
                    applicability = parsed['applicability']
                
                # Определяем характеристики
                characteristics = str(row.get('characteristics', '')).strip()
                if not characteristics and parsed.get('characteristics'):
                    characteristics = parsed['characteristics']
                elif characteristics and parsed.get('characteristics'):
                    # Объединяем существующие и новые характеристики
                    characteristics = f"{characteristics}\n{parsed['characteristics']}"
                
                # Формируем cross_numbers из OEM номера
                cross_numbers_parts = []
                if oem_number:
                    cross_numbers_parts.append(oem_number)
                if row.get('cross_numbers'):
                    cross_numbers_parts.append(str(row['cross_numbers']).strip())
                cross_numbers = ', '.join([p for p in cross_numbers_parts if p]) if cross_numbers_parts else ''
                
                # Определяем бренд
                # Приоритет: явно указанный бренд в данных > автоматически определенный из названия
                if auto_brand:
                    # Если бренд явно указан в данных, используем его (даже если он не в списке известных)
                    explicit_brand = row.get('brand', '').strip()
                    if explicit_brand:
                        brand = explicit_brand
                    else:
                        # Если бренд не указан, пытаемся определить автоматически
                        brand = parsed['brand'] or ''
                else:
                    # Если auto_brand=False, используем только явно указанный бренд
                    brand = row.get('brand', '').strip()
                
                # Определяем категорию
                category = get_category_for_product(name) if auto_category else None
                
                # Обрабатываем розничную цену
                price_value = 0
                if row.get('price_num') is not None:
                    try:
                        price_value = float(row['price_num'])
                    except (ValueError, TypeError):
                        price_value = 0
                elif row.get('price'):
                    price_str = str(row['price']).strip()
                    if price_str and price_str.lower() not in ['none', 'null', '']:
                        price_str = price_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
                        try:
                            price_value = float(price_str)
                        except (ValueError, TypeError):
                            price_value = 0
                
                # Обрабатываем ОПТОВУЮ цену
                wholesale_price_value = None
                if row.get('wholesale_price_num') is not None:
                    try:
                        wholesale_price_value = float(row['wholesale_price_num'])
                    except (ValueError, TypeError):
                        wholesale_price_value = None
                elif row.get('wholesale_price'):
                    wp_str = str(row['wholesale_price']).strip()
                    if wp_str and wp_str.lower() not in ['none', 'null', '']:
                        wp_str = wp_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
                        try:
                            wholesale_price_value = float(wp_str)
                        except (ValueError, TypeError):
                            wholesale_price_value = None
                
                # Обрабатываем остаток
                quantity_value = 0
                if row.get('quantity_num') is not None:
                    try:
                        quantity_value = int(float(row['quantity_num']))
                    except (ValueError, TypeError):
                        quantity_value = 0
                elif row.get('quantity'):
                    quantity_str = str(row['quantity']).strip()
                    if quantity_str and quantity_str.lower() not in ['none', 'null', '']:
                        quantity_str = quantity_str.replace(' ', '').replace('\xa0', '').replace(',', '')
                        try:
                            quantity_value = int(float(quantity_str))
                        except (ValueError, TypeError):
                            quantity_value = 0
                
                # Определяем наличие
                availability = 'out_of_stock' if quantity_value == 0 else 'in_stock'
                
                # Ищем товар ТОЛЬКО в партнёрском каталоге!
                product = None
                if article:
                    product = Product.objects.filter(
                        article=article, 
                        catalog_type='wholesale'
                    ).first()
                
                if not product:
                    product = Product.objects.filter(
                        name=name, 
                        catalog_type='wholesale'
                    ).first()
                
                if product and update_existing:
                    # Обновляем существующий партнёрский товар
                    product.name = name
                    if brand:
                        product.brand = brand
                    if category:
                        product.category = category
                    if article:
                        product.article = article
                    if cross_numbers:
                        product.cross_numbers = cross_numbers
                    if applicability:
                        product.applicability = applicability
                    if characteristics:
                        # Объединяем с существующими характеристиками, если есть
                        existing_chars = product.characteristics or ''
                        if existing_chars:
                            product.characteristics = f"{existing_chars}\n{characteristics}"
                        else:
                            product.characteristics = characteristics
                    if price_value > 0:
                        product.price = price_value
                    if wholesale_price_value is not None:
                        product.wholesale_price = wholesale_price_value
                    if quantity_value >= 0:
                        product.quantity = quantity_value
                    product.availability = availability
                    product.save()
                    stats['updated'] += 1
                elif not product:
                    # Создаём новый товар в ПАРТНЁРСКОМ каталоге
                    product = Product.objects.create(
                        name=name,
                        article=article,
                        brand=brand,
                        category=category,
                        cross_numbers=cross_numbers,
                        applicability=applicability,
                        characteristics=characteristics,
                        price=price_value,
                        wholesale_price=wholesale_price_value,
                        catalog_type='wholesale',  # ПАРТНЁРСКИЙ КАТАЛОГ!
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

