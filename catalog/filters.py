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
        """Поиск по названию, артикулу, бренду и кросс-номерам (по частичным совпадениям слов)."""
        if not value or not value.strip():
            return queryset
        
        # Разбиваем запрос на отдельные слова (минимум 2 символа)
        query_words = [word.strip() for word in value.split() if len(word.strip()) >= 2]
        
        if not query_words:
            # Если слово слишком короткое, ищем весь запрос целиком
            query_words = [value.strip()]
        
        # Для каждого слова создаём условие поиска
        # Используем AND - товар должен содержать ВСЕ слова из запроса
        for word in query_words:
            word_q = (
                models.Q(name__icontains=word) |
                models.Q(article__icontains=word) |
                models.Q(brand__icontains=word) |
                models.Q(cross_numbers__icontains=word) |
                models.Q(applicability__icontains=word)
            )
            queryset = queryset.filter(word_q)
        
        return queryset


def get_brand_choices(category=None):
    """
    Получить список брендов для фильтра.
    Показывает ВСЕ активные бренды из справочника.
    """
    from .models import Brand
    
    # Получаем все активные бренды из справочника
    active_brands = Brand.objects.filter(is_active=True).order_by('name').values_list('name', flat=True)
    
    return [(b, b) for b in active_brands if b]

