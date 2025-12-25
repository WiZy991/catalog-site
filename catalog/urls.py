from django.urls import path, re_path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.CatalogView.as_view(), name='index'),
    path('search/', views.search_products, name='search'),
    path('filter/', views.filter_products_ajax, name='filter'),
    path('product/<slug:slug>/', views.ProductView.as_view(), name='product_simple'),
    # Универсальный паттерн для категорий и товаров
    # Сначала пробуем товар, если не найден - пробуем категорию
    re_path(r'^(?P<category_path>[\w/-]+)/(?P<slug>[\w-]+)/$', views.CatalogItemView.as_view(), name='product'),
    # Паттерн для категорий (1 или более сегментов)
    re_path(r'^(?P<path>[\w/-]+)/$', views.CategoryView.as_view(), name='category'),
]

