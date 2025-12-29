from django.conf import settings
from .models import Category


def categories_processor(request):
    """Контекстный процессор для категорий."""
    from django.db.models import Prefetch
    root_categories = Category.objects.filter(
        parent=None, 
        is_active=True
    ).order_by('order', 'name').prefetch_related(
        Prefetch(
            'children',
            queryset=Category.objects.filter(is_active=True).order_by('order', 'name')
        )
    )
    return {
        'root_categories': root_categories,
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'Каталог'),
        'COMPANY_NAME': getattr(settings, 'COMPANY_NAME', getattr(settings, 'SITE_NAME', 'Каталог')),
        'SITE_DESCRIPTION': getattr(settings, 'SITE_DESCRIPTION', ''),
        'SITE_PHONE': getattr(settings, 'SITE_PHONE', ''),
        'SITE_PHONE_2': getattr(settings, 'SITE_PHONE_2', ''),
        'SITE_EMAIL': getattr(settings, 'SITE_EMAIL', ''),
        'SITE_EMAILS': getattr(settings, 'SITE_EMAILS', [{'email': getattr(settings, 'SITE_EMAIL', ''), 'label': getattr(settings, 'SITE_EMAIL', '')}]),
        'SITE_ADDRESS': getattr(settings, 'SITE_ADDRESS', ''),
        'SITE_HOURS': getattr(settings, 'SITE_HOURS', ''),
        'FARPOST_PROFILE_URL': getattr(settings, 'FARPOST_PROFILE_URL', ''),
        'SITE_LOGO': getattr(settings, 'SITE_LOGO', None),
        'SITE_LOGO_WIDTH': getattr(settings, 'SITE_LOGO_WIDTH', 200),
        'WHATSAPP_URL': getattr(settings, 'WHATSAPP_URL', None),
        'TELEGRAM_URL': getattr(settings, 'TELEGRAM_URL', None),
        'MAX_URL': getattr(settings, 'MAX_URL', None),
        'MAX_OPT_URL': getattr(settings, 'MAX_OPT_URL', None),
        'COMPANY_OWNER': getattr(settings, 'COMPANY_OWNER', ''),
        'COMPANY_INN': getattr(settings, 'COMPANY_INN', ''),
        'COMPANY_OGRN': getattr(settings, 'COMPANY_OGRN', ''),
    }

