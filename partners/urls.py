from django.urls import path
from . import views

app_name = 'partners'

urlpatterns = [
    # Главная страница раздела для партнёров
    path('', views.WholesaleView.as_view(), name='wholesale'),
    
    # Регистрация партнёра
    path('register/', views.PartnerRegisterView.as_view(), name='register'),
    path('register/success/', views.PartnerRegisterSuccessView.as_view(), name='register_success'),
    
    # Авторизация партнёра
    path('login/', views.PartnerLoginView.as_view(), name='login'),
    path('logout/', views.PartnerLogoutView.as_view(), name='logout'),
    
    # Профиль партнёра
    path('profile/', views.PartnerProfileView.as_view(), name='profile'),
    path('profile/edit/', views.PartnerProfileEditView.as_view(), name='profile_edit'),
    path('profile/change-password/', views.PartnerPasswordChangeView.as_view(), name='password_change'),
    
    # Каталог для авторизованных партнёров (с ценами)
    path('catalog/', views.PartnerCatalogView.as_view(), name='catalog'),
    path('catalog/<slug:category_slug>/', views.PartnerCatalogView.as_view(), name='catalog_category'),
    path('product/<slug:slug>/', views.PartnerProductView.as_view(), name='product'),
    
    # Публичный каталог (без цен)
    path('browse/', views.PublicPartnerCatalogView.as_view(), name='public_catalog'),
    path('browse/<slug:category_slug>/', views.PublicPartnerCatalogView.as_view(), name='public_catalog_category'),
    path('browse/product/<slug:slug>/', views.PublicPartnerProductView.as_view(), name='public_product'),
    
    # Заказы партнёров
    path('orders/', views.PartnerOrdersView.as_view(), name='orders'),
    path('orders/create/', views.partner_order_create, name='order_create'),
    path('orders/<int:order_id>/confirm/', views.partner_order_confirm, name='order_confirm'),
    path('orders/<int:order_id>/item/<int:item_id>/remove/', views.partner_order_item_remove, name='order_item_remove'),
    path('orders/export/', views.partner_orders_export_xls, name='orders_export'),
    
    # Корзина партнёра
    path('cart/add/<int:product_id>/', views.partner_cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.partner_cart_update, name='cart_update'),
    path('cart/count/', views.partner_cart_count, name='cart_count'),
]
