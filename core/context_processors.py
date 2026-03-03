"""
Context processors для SEO и общих данных сайта.
"""
from django.conf import settings


def seo_processor(request):
    """
    Context processor для SEO данных.
    Добавляет в контекст всех шаблонов SEO-информацию.
    """
    try:
        # Определяем канонический домен
        host = request.get_host()
        scheme = request.scheme
        
        # Определяем, какой домен использовать как канонический
        # Если это временный домен, используем его, иначе основной
        # Защита от отсутствующих настроек
        if 'beget.tech' in host:
            canonical_domain = getattr(settings, 'SITE_DOMAIN_TEMP', host)
        else:
            # Проверяем, есть ли www в домене
            if host.startswith('www.'):
                canonical_domain = getattr(settings, 'SITE_DOMAIN_WWW', host)
            else:
                canonical_domain = getattr(settings, 'SITE_DOMAIN', host)
        
        # Формируем базовый URL
        base_url = f"{scheme}://{canonical_domain}"
        
        # Получаем текущий полный URL для canonical
        try:
            current_url = request.build_absolute_uri()
            # Заменяем домен на канонический
            if request.get_host() != canonical_domain:
                current_url = current_url.replace(f"{scheme}://{request.get_host()}", base_url)
        except Exception:
            current_url = base_url
        
        # Получаем изображение для Open Graph (логотип сайта)
        og_image = None
        if hasattr(settings, 'SITE_LOGO') and settings.SITE_LOGO:
            og_image = f"{base_url}{settings.STATIC_URL}{settings.SITE_LOGO}"
        else:
            # Используем дефолтное изображение, если логотип не задан
            og_image = f"{base_url}{settings.STATIC_URL}images/logo.png"
        
        # Убеждаемся, что canonical_url всегда имеет значение
        if not current_url:
            current_url = base_url
        
        return {
            'SEO_BASE_URL': base_url,
            'SEO_CANONICAL_URL': current_url,
            'SEO_OG_IMAGE': og_image or f"{base_url}{settings.STATIC_URL}images/logo.png",
            'SEO_KEYWORDS': getattr(settings, 'SITE_KEYWORDS', ''),
            'SEO_LOCALE': getattr(settings, 'SITE_LOCALE', 'ru_RU'),
            'SEO_LANGUAGE': getattr(settings, 'SITE_LANGUAGE', 'ru'),
            'SEO_OG_TYPE': getattr(settings, 'SITE_OG_TYPE', 'website'),
            'SEO_TWITTER_CARD': getattr(settings, 'SITE_TWITTER_CARD', 'summary_large_image'),
            'SEO_TWITTER_SITE': getattr(settings, 'SITE_TWITTER_SITE', ''),
            'YANDEX_VERIFICATION': getattr(settings, 'YANDEX_VERIFICATION', ''),
            'GOOGLE_VERIFICATION': getattr(settings, 'GOOGLE_VERIFICATION', ''),
            'YANDEX_METRICA_ID': getattr(settings, 'YANDEX_METRICA_ID', ''),
        }
    except Exception as e:
        # В случае любой ошибки возвращаем безопасные значения по умолчанию
        # Это предотвратит падение сайта из-за ошибок в context processor
        try:
            host = request.get_host()
            scheme = request.scheme
            base_url = f"{scheme}://{host}"
        except Exception:
            base_url = "https://onesimus25.ru/"
        
        return {
            'SEO_BASE_URL': base_url,
            'SEO_CANONICAL_URL': base_url,
            'SEO_OG_IMAGE': f"{base_url}{settings.STATIC_URL}images/logo.png",
            'SEO_KEYWORDS': '',
            'SEO_LOCALE': 'ru_RU',
            'SEO_LANGUAGE': 'ru',
            'SEO_OG_TYPE': 'website',
            'SEO_TWITTER_CARD': 'summary_large_image',
            'SEO_TWITTER_SITE': '',
            'YANDEX_VERIFICATION': '',
            'GOOGLE_VERIFICATION': '',
            'YANDEX_METRICA_ID': '',
        }
