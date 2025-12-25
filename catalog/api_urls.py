"""
URL маршруты для API интеграции с 1С.
"""
from django.urls import path
from . import api_views

app_name = 'api_1c'

urlpatterns = [
    path('', api_views.one_c_import, name='import'),
]

