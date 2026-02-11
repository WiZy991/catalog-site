"""
URL маршруты для API интеграции с 1С.
"""
from django.urls import path
from . import api_views
from . import one_c_views

app_name = 'api_1c'

urlpatterns = [
    # Старый endpoint (для обратной совместимости)
    path('', api_views.one_c_import, name='import'),
    
    # Новые endpoints для полноценной интеграции
    path('sync/', one_c_views.one_c_api_view, name='sync'),
    path('upload/', one_c_views.file_upload_view, name='upload'),
]

