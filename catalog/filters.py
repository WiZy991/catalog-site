import django_filters
from django import forms
from django.db import models
from .models import Product, Category
from .search_utils import apply_product_search


SITE_AVAILABILITY_CHOICES = [
    ('in_stock', 'В наличии'),
    ('out_of_stock', 'Нет в наличии'),
]


class ProductFilter(django_filters.FilterSet):
    """Фильтр для товаров."""
    
    price_min = django_filters.NumberFilter(
        field_name='price', 
        lookup_expr='gte',
        label='Цена от'
    )
    price_max = django_filters.NumberFilter(
        field_name='price', 
        lookup_expr='lte',
        label='Цена до'
    )
    brand = django_filters.CharFilter(
        field_name='brand',
        lookup_expr='iexact',
        label='Бренд'
    )
    condition = django_filters.ChoiceFilter(
        choices=Product.CONDITION_CHOICES,
        label='Состояние'
    )
    availability = django_filters.ChoiceFilter(
        method='filter_availability',
        choices=SITE_AVAILABILITY_CHOICES,
        label='Наличие',
    )
    search = django_filters.CharFilter(
        method='filter_search',
        label='Поиск'
    )
    cross_number = django_filters.CharFilter(
        field_name='cross_numbers',
        lookup_expr='icontains',
        label='Кросс-номер'
    )
    applicability = django_filters.CharFilter(
        field_name='applicability',
        lookup_expr='icontains',
        label='Применимость'
    )

    class Meta:
        model = Product
        fields = ['brand', 'condition', 'availability']

    def filter_availability(self, queryset, name, value):
        """На сайте только «в наличии» и «нет в наличии» (без «под заказ»)."""
        if not value:
            return queryset
        if value == 'order':
            value = 'out_of_stock'
        if value == 'in_stock':
            return queryset.filter(quantity__gt=0, availability='in_stock')
        if value == 'out_of_stock':
            return queryset.exclude(quantity__gt=0, availability='in_stock')
        return queryset

    def filter_search(self, queryset, name, value):
        """Поиск по названию, артикулам, бренду, кросс-номерам и характеристикам."""
        if not value or not value.strip():
            return queryset
        return apply_product_search(queryset, value)


def get_brand_choices(category=None):
    """
    Получить список брендов для фильтра.
    Показывает ВСЕ активные бренды из справочника.
    """
    from .models import Brand
    
    # Получаем все активные бренды из справочника
    active_brands = Brand.objects.filter(is_active=True).order_by('name').values_list('name', flat=True)
    
    return [(b, b) for b in active_brands if b]

