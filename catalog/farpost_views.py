"""
Views для автоматической выгрузки прайс-листа для Farpost.
Farpost периодически загружает прайс-лист по указанной ссылке.
"""
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.conf import settings
from .models import Product
from .services import generate_farpost_api_file


@require_http_methods(["GET"])
def farpost_price_list(request, file_format=None):
    """
    Генерирует и возвращает прайс-лист для Farpost.
    
    Farpost периодически загружает этот файл по указанной ссылке.
    
    Параметры:
    - file_format: формат файла (csv, xls, xml). Определяется из URL.
    
    Примеры URL:
    - /farpost/price-list.csv
    - /farpost/price-list.xls
    - /farpost/price-list.xml
    """
    # Определяем формат из URL, если не передан
    if not file_format:
        # Пытаемся определить из пути
        path = request.path.lower()
        if path.endswith('.xml'):
            file_format = 'xml'
        elif path.endswith('.xls'):
            file_format = 'xls'
        else:
            file_format = 'csv'
    
    # Получаем все активные товары из основного каталога
    # ВАЖНО: Экспортируем только товары с остатком (quantity > 0)
    products = Product.objects.filter(
        is_active=True,
        catalog_type='retail',
        quantity__gt=0  # Только товары с остатком больше 0
    ).select_related('category').prefetch_related('images')
    
    # Нормализуем формат
    file_format = file_format.lower()
    if file_format not in ['csv', 'xls', 'xml']:
        file_format = 'csv'
    
    # Генерируем файл
    try:
        file_content, filename, content_type = generate_farpost_api_file(
            products=products,
            file_format=file_format,
            request=request
        )
        
        # Создаем HTTP ответ
        response = HttpResponse(file_content, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        # Добавляем заголовки для кеширования (опционально)
        # Farpost будет загружать файл периодически, поэтому можно кешировать на короткое время
        response['Cache-Control'] = 'public, max-age=300'  # 5 минут
        
        return response
        
    except Exception as e:
        # В случае ошибки возвращаем сообщение об ошибке
        error_message = f'Ошибка генерации прайс-листа: {str(e)}'
        return HttpResponse(error_message, status=500, content_type='text/plain; charset=utf-8')
