"""Общая логика поиска товаров на витрине."""
import re

from django.db.models import Q


def product_search_words(query: str) -> list[str]:
    query = (query or '').strip()
    if not query:
        return []
    words = [word.strip() for word in query.split() if len(word.strip()) >= 2]
    return words or [query]


def product_search_word_q(word: str) -> Q:
    """OR по одному слову/фрагменту запроса (артикул, OEM, название, характеристики)."""
    if not word:
        return Q(pk__in=[])

    word_escaped = re.escape(word)
    return (
        Q(name__icontains=word)
        | Q(article__icontains=word)
        | Q(supplier_article__icontains=word)
        | Q(brand__icontains=word)
        | Q(cross_numbers__icontains=word)
        | Q(applicability__icontains=word)
        | Q(characteristics__icontains=word)
        | Q(description__icontains=word)
        | Q(short_description__icontains=word)
        | Q(external_id__icontains=word)
        | Q(name__iregex=word_escaped)
        | Q(article__iregex=word_escaped)
        | Q(supplier_article__iregex=word_escaped)
        | Q(brand__iregex=word_escaped)
        | Q(cross_numbers__iregex=word_escaped)
        | Q(applicability__iregex=word_escaped)
        | Q(characteristics__iregex=word_escaped)
    )


def apply_product_search(queryset, query: str):
    """AND по словам запроса."""
    for word in product_search_words(query):
        queryset = queryset.filter(product_search_word_q(word))
    return queryset
