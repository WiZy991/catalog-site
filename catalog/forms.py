"""
Формы для админки каталога.
"""
from django import forms
from django.core.validators import FileExtensionValidator


class MultipleFileInput(forms.FileInput):
    """Кастомный виджет для загрузки нескольких файлов."""
    allow_multiple_selected = True
    
    def __init__(self, attrs=None):
        default_attrs = {'multiple': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class MultipleFileField(forms.FileField):
    """Поле для загрузки нескольких файлов."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class BulkImageUploadForm(forms.Form):
    """Форма массовой загрузки изображений."""
    images = MultipleFileField(
        label='Изображения',
        widget=MultipleFileInput(attrs={
            'accept': 'image/*',
            'class': 'form-control',
        }),
        help_text='Выберите несколько изображений. Имя файла должно содержать артикул товара (например: 23300-78090.jpg, ME220745_1.jpg)'
    )
    create_products = forms.BooleanField(
        label='Создавать товары, если не найдены',
        required=False,
        initial=False,
        help_text='Если товар не найден по артикулу, создать новый товар из имени файла'
    )


class BulkProductImportForm(forms.Form):
    """Форма массового импорта товаров."""
    file = forms.FileField(
        label='Файл данных',
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'xls', 'xlsx', 'xml'])],
        widget=forms.FileInput(attrs={
            'accept': '.csv,.xls,.xlsx,.xml',
            'class': 'form-control',
        }),
        help_text='Загрузите CSV, Excel или XML файл с товарами (поддерживается CommerceML 2 формат)'
    )
    auto_category = forms.BooleanField(
        label='Автоматически определять категории',
        required=False,
        initial=True,
        help_text='Категории будут созданы автоматически по ключевым словам в названии'
    )
    auto_brand = forms.BooleanField(
        label='Автоматически определять бренды',
        required=False,
        initial=True,
        help_text='Бренды будут определены по известным названиям в тексте'
    )
    update_existing = forms.BooleanField(
        label='Обновлять существующие товары',
        required=False,
        initial=True,
        help_text='Если товар с таким артикулом уже есть, обновить его данные'
    )


class QuickProductForm(forms.Form):
    """Форма быстрого добавления товара (минимум данных)."""
    name = forms.CharField(
        label='Название товара',
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Стартер Isuzu 10PD1 24V ME220745'
        }),
        help_text='Введите название. Бренд, артикул и категория определятся автоматически.'
    )
    price = forms.DecimalField(
        label='Цена',
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00'
        })
    )
    image = forms.ImageField(
        label='Фото',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )


class CategoryMappingForm(forms.Form):
    """Форма для настройки маппинга категорий."""
    keywords = forms.CharField(
        label='Ключевые слова',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'стартер, starter, пускатель'
        }),
        help_text='Введите ключевые слова через запятую'
    )


# Форма для FarpostAPISettings будет определена в admin.py