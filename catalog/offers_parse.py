"""
Парсинг offers.xml (CommerceML 2) для сверки с витриной.
Логика извлечения полей согласована с process_offers_file_single_pass.
"""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple

RETAIL_PRICE_TYPE_ID = 'f6708032-0bd5-11f1-811f-00155d01d802'
WHOLESALE_PRICE_TYPE_ID = 'b12f44c0-1208-11f1-811f-00155d01d802'

SUPPLIER_ARTICLE_NAMES = frozenset(
    ['артикул1', 'артикул 1', 'article1', 'article 1', 'артикул', 'article']
)
NUMBER_NAMES = frozenset(
    ['номер', 'number', 'номер детали', 'part number', 'partnumber']
)
CROSS_NUMBER_NAMES = frozenset(
    ['артикул2', 'артикул 2', 'article2', 'article 2', 'oem', 'oem номер']
)


def _local_tag(tag: str) -> str:
    if tag and tag.startswith('{'):
        return tag.split('}', 1)[1]
    return tag


def _find(elem: ET.Element, tag: str, namespace: Optional[str]) -> Optional[ET.Element]:
    if namespace:
        x = elem.find(f'.//{{{namespace}}}{tag}')
        if x is not None:
            return x
    return elem.find(f'.//{tag}')


def _iter_property_items(root_elem: Optional[ET.Element], namespace: Optional[str]) -> List[ET.Element]:
    if root_elem is None:
        return []
    if namespace:
        items = root_elem.findall(f'{{{namespace}}}ЗначенияСвойства')
        if items:
            return items
    return root_elem.findall('ЗначенияСвойства')


def _iter_char_items(root_elem: Optional[ET.Element]) -> List[ET.Element]:
    if root_elem is None:
        return []
    return list(root_elem.findall('.//*'))


def _property_pairs(offer_elem: ET.Element, namespace: Optional[str]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for root_name in ('ХарактеристикиТовара', 'ЗначенияСвойств'):
        root_elem = _find(offer_elem, root_name, namespace)
        if root_elem is None:
            continue
        if root_name == 'ЗначенияСвойств':
            items = _iter_property_items(root_elem, namespace)
        else:
            items = _iter_char_items(root_elem)
        for item in items:
            name_elem = _find(item, 'Наименование', namespace)
            value_elem = _find(item, 'Значение', namespace)
            if name_elem is None or value_elem is None or not name_elem.text or not value_elem.text:
                continue
            pairs.append((name_elem.text.strip(), value_elem.text.strip()))
    return pairs


def _extract_supplier_article(offer_elem: ET.Element, namespace: Optional[str]) -> str:
    for name, value in _property_pairs(offer_elem, namespace):
        if name.strip().lower() in SUPPLIER_ARTICLE_NAMES and value:
            return value
    name_elem = _find(offer_elem, 'Наименование', namespace)
    raw_name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else ''
    if raw_name and '(' in raw_name and ')' in raw_name:
        inside = raw_name[raw_name.find('(') + 1: raw_name.rfind(')')]
        parts = [p.strip() for p in inside.split(',') if p.strip()]
        if len(parts) >= 2:
            return parts[1]
    return ''


def _extract_number(offer_elem: ET.Element, namespace: Optional[str]) -> str:
    for name, value in _property_pairs(offer_elem, namespace):
        if name.strip().lower() in NUMBER_NAMES and value:
            return value
    return ''


def _extract_cross_number_keys(offer_elem: ET.Element, namespace: Optional[str]) -> List[str]:
    keys: List[str] = []
    seen = set()
    for name, value in _property_pairs(offer_elem, namespace):
        n = name.strip().lower()
        if n in CROSS_NUMBER_NAMES or n in SUPPLIER_ARTICLE_NAMES:
            v = value.strip()
            if v and v.upper() not in seen:
                seen.add(v.upper())
                keys.append(v)
    return keys


def _parse_prices(offer_elem: ET.Element, namespace: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    retail_price = None
    wholesale_price = None
    prices_elem = _find(offer_elem, 'Цены', namespace)
    if prices_elem is None:
        return retail_price, wholesale_price
    if namespace:
        price_elems = prices_elem.findall(f'{{{namespace}}}Цена')
    else:
        price_elems = []
    if not price_elems:
        price_elems = prices_elem.findall('Цена')
    for price_elem in price_elems:
        type_elem = _find(price_elem, 'ИдТипаЦены', namespace)
        val_elem = _find(price_elem, 'ЦенаЗаЕдиницу', namespace)
        if type_elem is None or val_elem is None or not type_elem.text or not val_elem.text:
            continue
        try:
            val = float(val_elem.text.strip().replace(',', '.').replace(' ', '').replace('\xa0', ''))
        except (ValueError, TypeError):
            continue
        if val <= 0:
            continue
        type_id = type_elem.text.strip()
        if type_id == RETAIL_PRICE_TYPE_ID:
            retail_price = val
        elif type_id == WHOLESALE_PRICE_TYPE_ID:
            wholesale_price = val
    return retail_price, wholesale_price


def _parse_quantity(offer_elem: ET.Element, namespace: Optional[str]) -> int:
    if namespace:
        qty_elems = offer_elem.findall(f'.//{{{namespace}}}Количество')
    else:
        qty_elems = []
    if not qty_elems:
        qty_elems = offer_elem.findall('.//Количество')
    total = 0
    found = False
    for q in qty_elems:
        if q is None or q.text is None:
            continue
        try:
            total += int(float(q.text.strip().replace(',', '.')))
            found = True
        except (ValueError, TypeError):
            continue
    if found:
        return total
    if namespace:
        warehouse_elems = offer_elem.findall(f'.//{{{namespace}}}Склад')
    else:
        warehouse_elems = []
    if not warehouse_elems:
        warehouse_elems = offer_elem.findall('.//Склад')
    total = 0
    found = False
    for w in warehouse_elems:
        raw = w.get('КоличествоНаСкладе') or w.get('QuantityInStock')
        if not raw:
            continue
        try:
            total += int(float(str(raw).strip().replace(',', '.')))
            found = True
        except (ValueError, TypeError):
            continue
    return total if found else 0


def parse_offer_element(offer_elem: ET.Element, namespace: Optional[str] = None) -> Dict[str, Any]:
    """Разбирает один элемент Предложение в словарь для сверки."""
    if namespace is None:
        ns_match = re.match(r'^\{([^}]+)\}', offer_elem.tag)
        namespace = ns_match.group(1) if ns_match else None

    product_id_elem = _find(offer_elem, 'Ид', namespace)
    external_id = product_id_elem.text.strip() if (product_id_elem is not None and product_id_elem.text) else ''

    name_elem = _find(offer_elem, 'Наименование', namespace)
    name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else ''

    supplier_article = _extract_supplier_article(offer_elem, namespace)
    number_article = _extract_number(offer_elem, namespace)
    article = (supplier_article or number_article or '').strip()
    oem_keys = _extract_cross_number_keys(offer_elem, namespace)
    quantity = _parse_quantity(offer_elem, namespace)
    retail_price, wholesale_price = _parse_prices(offer_elem, namespace)

    article_keys = []
    seen = set()
    for key in [article, supplier_article, number_article] + oem_keys:
        k = (key or '').strip()
        if not k:
            continue
        ku = k.upper()
        if ku not in seen:
            seen.add(ku)
            article_keys.append(k)

    return {
        'external_id': external_id,
        'name': name,
        'article': article,
        'supplier_article': supplier_article,
        'number_article': number_article,
        'oem_keys': oem_keys,
        'article_keys': article_keys,
        'quantity': quantity,
        'retail_price': retail_price,
        'wholesale_price': wholesale_price,
    }


def _open_offers_xml(file_path: str) -> BinaryIO:
    """
    Открывает offers-файл для iterparse.
    Пропускает строку браузера «This XML file does not appear...»,
    если файл сохранён из Chrome/Firefox как .txt.
    """
    with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        content = f.read()
    stripped = content.lstrip()
    if stripped.startswith('This XML file does not appear'):
        idx = content.find('<?xml')
        if idx < 0:
            nl = content.find('\n<')
            idx = nl + 1 if nl >= 0 else content.find('<')
        if idx >= 0:
            content = content[idx:]
    return io.BytesIO(content.encode('utf-8'))


def detect_namespace(xml_source: BinaryIO) -> Optional[str]:
    xml_source.seek(0)
    for event, elem in ET.iterparse(xml_source, events=('start',)):
        if elem.tag.startswith('{'):
            return elem.tag[1:].split('}')[0]
        break
    return None


def iter_offers_from_file(file_path: str) -> Iterator[Dict[str, Any]]:
    """Потоковый разбор всех Предложение из файла offers."""
    xml_source = _open_offers_xml(file_path)
    namespace = detect_namespace(xml_source)
    xml_source.seek(0)
    for event, elem in ET.iterparse(xml_source, events=('end',)):
        if _local_tag(elem.tag) != 'Предложение':
            continue
        yield parse_offer_element(elem, namespace)
        elem.clear()
