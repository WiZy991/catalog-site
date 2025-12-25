from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.http import HttpResponse
from catalog.models import Category, Product
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
        context['new_products'] = Product.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related('images').order_by('-created_at')[:8]
        context['categories'] = Category.objects.filter(
            parent=None, 
            is_active=True
        ).order_by('order', 'name')[:6]
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

