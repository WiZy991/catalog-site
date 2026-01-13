from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contacts/', views.ContactsView.as_view(), name='contacts'),
    path('payment-delivery/', views.PaymentDeliveryView.as_view(), name='payment_delivery'),
    path('public-offer/', views.PublicOfferView.as_view(), name='public_offer'),
    path('robots.txt', views.robots_txt, name='robots'),
]

