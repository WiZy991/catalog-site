import django_filters
from django import forms
from django.db import models
from .models import Product, Category


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
        choices=Product.AVAILABILITY_CHOICES,
        label='Наличие'
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

    def filter_search(self, queryset, name, value):
        """Поиск по названию, артикулу, бренду и кросс-номерам."""
        return queryset.filter(
            models.Q(name__icontains=value) |
            models.Q(article__icontains=value) |
            models.Q(brand__icontains=value) |
            models.Q(cross_numbers__icontains=value) |
            models.Q(applicability__icontains=value)
        )


def get_brand_choices(category=None):
    """Получить список брендов для фильтра."""
    queryset = Product.objects.filter(is_active=True).exclude(brand='')
    if category:
        descendants = category.get_descendants(include_self=True)
        queryset = queryset.filter(category__in=descendants)
    brands = queryset.values_list('brand', flat=True).distinct().order_by('brand')
    return [(b, b) for b in brands if b]

