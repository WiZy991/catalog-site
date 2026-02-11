"""
Serializers для валидации данных от 1С (без DRF).
"""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from .models import Product, ProductCharacteristic, Category


class ValidationError(Exception):
    """Кастомное исключение для валидации."""
    def __init__(self, message, errors=None):
        self.message = message
        self.errors = errors or {}
        super().__init__(self.message)


def validate_product_characteristic(data):
    """Валидация характеристики товара."""
    errors = {}
    
    if 'name' not in data or not data['name']:
        errors['name'] = 'Название характеристики обязательно'
    elif len(data['name']) > 200:
        errors['name'] = 'Название характеристики не должно превышать 200 символов'
    
    if 'value' not in data or not data['value']:
        errors['value'] = 'Значение характеристики обязательно'
    elif len(data['value']) > 500:
        errors['value'] = 'Значение характеристики не должно превышать 500 символов'
    
    if errors:
        raise ValidationError('Ошибка валидации характеристики', errors)
    
    return {
        'name': str(data['name']).strip()[:200],
        'value': str(data['value']).strip()[:500],
    }


def validate_product(data):
    """Валидация товара."""
    errors = {}
    validated = {}
    
    # SKU (артикул) - обязательное поле
    if 'sku' not in data or not data['sku']:
        errors['sku'] = 'Артикул товара обязателен'
    else:
        sku = str(data['sku']).strip()
        if len(sku) > 100:
            errors['sku'] = 'Артикул не должен превышать 100 символов'
        else:
            validated['sku'] = sku
    
    # Название - обязательное поле
    if 'name' not in data or not data['name']:
        errors['name'] = 'Название товара обязательно'
    else:
        name = str(data['name']).strip()
        if len(name) > 500:
            errors['name'] = 'Название не должно превышать 500 символов'
        else:
            validated['name'] = name
    
    # Описание - опционально
    if 'description' in data and data['description']:
        validated['description'] = str(data['description']).strip()
    else:
        validated['description'] = ''
    
    # Цена - обязательное поле
    if 'price' not in data:
        errors['price'] = 'Цена обязательна'
    else:
        try:
            price = Decimal(str(data['price']).replace(',', '.'))
            if price < 0:
                errors['price'] = 'Цена не может быть отрицательной'
            else:
                validated['price'] = price
        except (ValueError, InvalidOperation, TypeError):
            errors['price'] = 'Неверный формат цены'
    
    # Старая цена - опционально
    if 'old_price' in data and data['old_price']:
        try:
            old_price = Decimal(str(data['old_price']).replace(',', '.'))
            if old_price < 0:
                errors['old_price'] = 'Старая цена не может быть отрицательной'
            elif 'price' in validated and old_price <= validated['price']:
                errors['old_price'] = 'Старая цена должна быть больше текущей цены'
            else:
                validated['old_price'] = old_price
        except (ValueError, InvalidOperation, TypeError):
            errors['old_price'] = 'Неверный формат старой цены'
    
    # Остаток на складе - опционально, по умолчанию 0
    if 'stock' in data and data['stock'] is not None:
        try:
            stock = int(float(str(data['stock']).replace(',', '.')))
            if stock < 0:
                errors['stock'] = 'Остаток не может быть отрицательным'
            else:
                validated['stock'] = stock
        except (ValueError, TypeError):
            errors['stock'] = 'Неверный формат остатка'
    else:
        validated['stock'] = 0
    
    # Категория - опционально
    if 'category' in data and data['category']:
        validated['category'] = str(data['category']).strip()[:200]
    else:
        validated['category'] = None
    
    # Характеристики - опционально
    if 'characteristics' in data and data['characteristics']:
        if isinstance(data['characteristics'], list):
            validated['characteristics'] = []
            for char_data in data['characteristics']:
                try:
                    validated_char = validate_product_characteristic(char_data)
                    validated['characteristics'].append(validated_char)
                except ValidationError as e:
                    errors.setdefault('characteristics', []).append(e.errors)
        else:
            errors['characteristics'] = 'Характеристики должны быть списком'
    else:
        validated['characteristics'] = []
    
    # Активность - опционально, по умолчанию True
    if 'is_active' in data:
        is_active = data['is_active']
        if isinstance(is_active, str):
            is_active = is_active.lower() in ('true', '1', 'да', 'yes')
        validated['is_active'] = bool(is_active)
    else:
        validated['is_active'] = True
    
    if errors:
        raise ValidationError('Ошибка валидации товара', errors)
    
    return validated


def validate_sync_request(data):
    """Валидация запроса синхронизации."""
    errors = {}
    validated = {}
    
    # Токен - обязательное поле
    if 'token' not in data or not data['token']:
        errors['token'] = 'Токен авторизации обязателен'
    else:
        from django.conf import settings
        expected_token = getattr(settings, 'ONE_C_API_KEY', '')
        if not expected_token:
            errors['token'] = 'Токен не настроен в системе'
        elif str(data['token']) != expected_token:
            errors['token'] = 'Неверный токен авторизации'
        else:
            validated['token'] = str(data['token'])
    
    # Товары - обязательное поле
    if 'products' not in data:
        errors['products'] = 'Список товаров обязателен'
    elif not isinstance(data['products'], list):
        errors['products'] = 'Товары должны быть списком'
    elif len(data['products']) == 0:
        errors['products'] = 'Список товаров не может быть пустым'
    else:
        validated['products'] = []
        for idx, product_data in enumerate(data['products']):
            try:
                validated_product = validate_product(product_data)
                validated['products'].append(validated_product)
            except ValidationError as e:
                errors.setdefault('products', []).append({
                    'index': idx,
                    'errors': e.errors
                })
    
    if errors:
        raise ValidationError('Ошибка валидации запроса', errors)
    
    return validated
