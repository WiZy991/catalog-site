"""
Middleware для логирования всех запросов к CommerceML обмену.
"""
import logging

logger = logging.getLogger('catalog.commerceml_views')


class CommerceMLLoggingMiddleware:
    """Middleware для логирования всех запросов к /cml/exchange/"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Логируем все запросы к CommerceML
        if 'cml/exchange' in request.path or '1c_exchange' in request.path:
            logger.info("=" * 80)
            logger.info("MIDDLEWARE: CommerceML запрос получен")
            logger.info(f"  Path: {request.path}")
            logger.info(f"  Method: {request.method}")
            logger.info(f"  GET: {dict(request.GET)}")
            logger.info(f"  POST data size: {len(request.body)} bytes")
            logger.info(f"  Cookies: {dict(request.COOKIES)}")
            logger.info(f"  Headers: Authorization={bool(request.META.get('HTTP_AUTHORIZATION'))}")
            logger.info(f"  IP: {request.META.get('REMOTE_ADDR', 'unknown')}")
            logger.info("=" * 80)
        
        response = self.get_response(request)
        
        # Логируем ответ
        if 'cml/exchange' in request.path or '1c_exchange' in request.path:
            logger.info(f"MIDDLEWARE: Ответ отправлен, статус: {response.status_code}")
            if hasattr(response, 'content'):
                content_preview = response.content[:100] if len(response.content) > 100 else response.content
                logger.info(f"  Content preview: {content_preview}")
        
        return response
