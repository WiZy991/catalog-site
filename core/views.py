from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.db import OperationalError
from django.conf import settings
from catalog.models import Category, Product, Promotion
from .models import Page


class HomeView(TemplateView):
    """Главная страница."""
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['featured_products'] = Product.objects.filter(
            is_active=True, 
            is_featured=True
        ).select_related('category').prefetch_related('images')[:8]
        context['categories'] = Category.objects.filter(
            parent=None, 
            is_active=True
        ).order_by('order', 'name')[:6]
        # Защита от ошибки, если миграции не применены
        try:
            context['promotions'] = Promotion.objects.filter(
                is_active=True
            ).order_by('order', '-id', '-created_at')
        except (OperationalError, Exception) as e:
            # Таблица еще не создана, миграции не применены, или другая ошибка
            context['promotions'] = []
            # В режиме отладки можно залогировать ошибку
            if settings.DEBUG:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error loading promotions: {e}")
        return context


class AboutView(TemplateView):
    """Страница О нас."""
    template_name = 'core/about.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            page = Page.objects.get(slug='about', is_active=True)
            context['page'] = page
        except Page.DoesNotExist:
            context['page'] = None
        return context


class ContactsView(TemplateView):
    """Страница Контакты."""
    template_name = 'core/contacts.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            page = Page.objects.get(slug='contacts', is_active=True)
            context['page'] = page
        except Page.DoesNotExist:
            context['page'] = None
        return context


class PaymentDeliveryView(TemplateView):
    """Страница Оплата и доставка."""
    template_name = 'core/payment_delivery.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            page = Page.objects.get(slug='payment-delivery', is_active=True)
            context['page'] = page
        except Page.DoesNotExist:
            context['page'] = None
        return context


class PublicOfferView(TemplateView):
    """Страница "Не является публичной офертой"."""
    template_name = 'core/public_offer.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            page = Page.objects.get(slug='public-offer', is_active=True)
            context['page'] = page
        except Page.DoesNotExist:
            context['page'] = None
        return context


def robots_txt(request):
    """Генерация robots.txt."""
    content = """User-agent: *
Allow: /

Sitemap: {scheme}://{host}/sitemap.xml

Disallow: /admin/
Disallow: /media/
Disallow: /static/
""".format(scheme=request.scheme, host=request.get_host())
    return HttpResponse(content, content_type='text/plain')

