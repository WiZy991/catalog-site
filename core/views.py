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
            is_featured=True,
            quantity__gt=0  # Только товары с остатком
        ).select_related('category').prefetch_related('images')[:8]
        from django.db.models import Count, Q
        from django.db import transaction
        
        # Получаем категории
        categories = Category.objects.filter(
            parent=None, 
            is_active=True
        ).order_by('name')[:6]
        
        # Для главной считаем счетчик так же, как на странице категории:
        # сумма отображаемых подкатегорий (только с product_count > 0).
        # Это устраняет расхождения "карточка категории" vs "скобки подкатегорий".
        for category in categories:
            active_children = category.children.filter(is_active=True)
            count = sum(child.product_count for child in active_children if child.product_count > 0)
            category.home_product_count = count
            category._product_count = count
        
        context['categories'] = categories
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


class PrivacyPolicyView(TemplateView):
    """Страница Политики в отношении обработки персональных данных."""
    template_name = 'core/privacy_policy.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            page = Page.objects.get(slug='privacy-policy', is_active=True)
            context['page'] = page
        except Page.DoesNotExist:
            context['page'] = None
        return context


class ConsentView(TemplateView):
    """Страница Согласия на обработку персональных данных."""
    template_name = 'core/consent.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            page = Page.objects.get(slug='consent', is_active=True)
            context['page'] = page
        except Page.DoesNotExist:
            context['page'] = None
        return context


class RecommendationsView(TemplateView):
    """Страница Правила применения рекомендательных технологий."""
    template_name = 'core/recommendations.html'


class WholesaleView(TemplateView):
    """Страница Оптовые продажи."""
    template_name = 'core/wholesale.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            page = Page.objects.get(slug='wholesale', is_active=True)
            context['page'] = page
        except Page.DoesNotExist:
            context['page'] = None
        return context


def robots_txt(request):
    """Генерация robots.txt с поддержкой обоих доменов и оптимизацией для Яндекс и Google."""
    from django.conf import settings
    
    # Определяем канонический домен для sitemap
    host = request.get_host()
    if 'beget.tech' in host:
        canonical_host = settings.SITE_DOMAIN_TEMP
    else:
        # Убираем www для единообразия (или оставляем, в зависимости от настроек)
        if host.startswith('www.'):
            canonical_host = settings.SITE_DOMAIN_WWW
        else:
            canonical_host = settings.SITE_DOMAIN
    
    # Формируем правильный URL для sitemap
    sitemap_url = f"{request.scheme}://{canonical_host}/sitemap.xml"
    
    content = f"""# robots.txt для {settings.SITE_NAME}
# Основной домен: {settings.SITE_DOMAIN}
# Домен с www: {settings.SITE_DOMAIN_WWW}
# Временный домен: {settings.SITE_DOMAIN_TEMP}

User-agent: *
Allow: /
Allow: /catalog/
Allow: /catalog/*/
Allow: /*/product/

# Запрещаем индексацию служебных разделов
Disallow: /admin/
Disallow: /admin/*
Disallow: /media/
Disallow: /static/
Disallow: /partners/
Disallow: /partners/*
Disallow: /cml/
Disallow: /api/
Disallow: /farpost/
Disallow: /orders/cart/
Disallow: /orders/checkout/
Disallow: /*?*page=
Disallow: /*?*sort=
Disallow: /*?*filter=

# Разрешаем основные страницы
Allow: /
Allow: /catalog/
Allow: /about/
Allow: /contacts/
Allow: /payment-delivery/
Allow: /wholesale/
Allow: /privacy-policy/
Allow: /consent/
Allow: /public-offer/

# Sitemap
Sitemap: {sitemap_url}

# Для поисковых систем - Google
User-agent: Googlebot
Allow: /
Allow: /catalog/
Allow: /catalog/*/
Allow: /*/product/

# Для поисковых систем - Яндекс
User-agent: Yandex
Allow: /
Allow: /catalog/
Allow: /catalog/*/
Allow: /*/product/
Crawl-delay: 1

# Яндекс - мобильный бот
User-agent: YandexMobileBot
Allow: /
Allow: /catalog/
Allow: /catalog/*/
Allow: /*/product/
Crawl-delay: 1

# Для поисковых систем - Bing
User-agent: Bingbot
Allow: /
Allow: /catalog/
Allow: /catalog/*/
Allow: /*/product/

# Блокируем плохих ботов
User-agent: AhrefsBot
Crawl-delay: 10

User-agent: SemrushBot
Crawl-delay: 10

User-agent: MJ12bot
Crawl-delay: 10
"""
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


def yandex_verification(request):
    """Файл верификации Яндекс.Вебмастер."""
    content = """<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
</head>
<body>Verification: a7cbaaadf29ce5db</body>
</html>"""
    return HttpResponse(content, content_type='text/html; charset=utf-8')

