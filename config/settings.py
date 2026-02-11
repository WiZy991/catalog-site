"""
Django settings for the catalog project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-change-this-in-production-abc123xyz789'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    
    # Third party apps
    'mptt',
    'django_filters',
    'import_export',
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Local apps
    'catalog.apps.CatalogConfig',
    'core.apps.CoreConfig',
    'orders.apps.OrdersConfig',
    'partners.apps.PartnersConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'catalog.context_processors.categories_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Vladivostok'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Import-Export settings
IMPORT_EXPORT_USE_TRANSACTIONS = True

# Pagination
PRODUCTS_PER_PAGE = 24

# Static files versioning (обновляйте при изменении CSS/JS)
STATIC_VERSION = '2.7'

# API для 1С
ONE_C_API_KEY = '1XV8XYzbGBNVsMKhV8jYZ6823o9Aw7JZjpuvSYQiAhdhsS2V6M2tyBCUAGvtwHZxrn1u2sDjzU6FQ9lECSnzvHgEeE1ZRuLcTwVlHPcM5pEwr6tZ9M04ptPLE1vZK81r'

# Настройки для стандартного протокола CommerceML 2 обмена с 1С
ONE_C_EXCHANGE_DIR = os.path.join(MEDIA_ROOT, '1c_exchange')  # Директория для временного хранения файлов обмена
ONE_C_FILE_LIMIT = 104857600  # Максимальный размер файла в байтах (100 MB)
ONE_C_SUPPORT_ZIP = True  # Поддержка ZIP сжатия

# Site info (for SEO and templates)
SITE_NAME = 'Onesimus'
COMPANY_NAME = 'Onesimus'
SITE_DESCRIPTION = 'Каталог автозапчастей с доставкой'
SITE_PHONE = '+7 (924) 424-87-77'
SITE_PHONE_2 = '+7 (914) 322-97-77'
SITE_EMAIL = 'onesimus25@mail.ru'

SITE_EMAILS = [
    {'email': 'onesimus25@mail.ru', 'label': 'onesimus25@mail.ru'},

]
SITE_ADDRESS = 'Приморский край, г. Уссурийск, ул. Котовского 17В'
SITE_HOURS = 'Пн-Сб с 9:00 до 17:00'
FARPOST_PROFILE_URL = 'https://www.farpost.ru/user/Onesimus125'

# Информация о компании (ИП)
COMPANY_OWNER = 'ИП Щербович Елена Николаевна'
COMPANY_INN = '250703414475'
COMPANY_OGRN = '319253600080189'

# Logo settings
SITE_LOGO = 'images/лого.jpg'  # Путь к логотипу относительно static
SITE_LOGO_WIDTH = 200  # Ширина логотипа в пикселях (для alt и размеров)

# Ссылки на мессенджеры
WHATSAPP_URL = 'https://wa.me/message/5ILUQN5XFXQJM1'
TELEGRAM_URL = 'https://t.me/onesimus25'
MAX_URL = 'https://max.ru/u/f9LHodD0cOJUPJ5eKac-UNkIj1TgWn7lUOi0_6YYJU3gehzF5Ouk3hRFS0g'
MAX_OPT_URL = 'https://max.ru/u/f9LHodD0cOKejElDOF7uUTTvaYDYc6GO4a6CfrntKspSX-TtJZ9vl2Y1_mI'

# Email settings for orders
MANAGER_EMAIL = 'onesimus25@mail.ru'  # Email менеджера для получения заказов
PARTNER_MANAGER_EMAIL = 'onesimus25@mail.ru'  # Email менеджера по опту
DEFAULT_FROM_EMAIL = 'onesimus25@mail.ru'

# SMTP настройки для Mail.ru
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.mail.ru'
EMAIL_PORT = 465
EMAIL_USE_SSL = True  # Для порта 465 используется SSL, а не TLS
EMAIL_USE_TLS = False  # TLS используется для порта 587
EMAIL_HOST_USER = 'onesimus25@mail.ru'
EMAIL_HOST_PASSWORD = 'R15MjG5p5kHh5eDKefHL'  # Пароль приложения Mail.ru
EMAIL_TIMEOUT = 10  # Таймаут подключения в секундах

# Jazzmin Admin Panel Settings
JAZZMIN_SETTINGS = {
    # Заголовок окна
    "site_title": "Onesimus Admin",
    
    # Заголовок на странице логина
    "site_header": "Onesimus",
    
    # Заголовок бренда
    "site_brand": "Onesimus",
    
    # Логотип (путь относительно static)
    "site_logo": None,
    
    # CSS классы для логотипа
    "site_logo_classes": None,
    
    # Иконка сайта (favicon)
    "site_icon": None,
    
    # Приветственный текст
    "welcome_sign": "Добро пожаловать в панель управления",
    
    # Copyright
    "copyright": "Onesimus",
    
    # Модель пользователя
    "user_avatar": None,
    
    ############
    # Top Menu #
    ############
    "topmenu_links": [
        {"name": "Главная", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Сайт", "url": "/", "new_window": True},
        {"name": "Быстрое добавление", "url": "/admin/catalog/quick-add/"},
        {"name": "Массовый импорт", "url": "/admin/catalog/bulk-import/"},
        {"name": "Массовый импорт (опт)", "url": "/admin/partners/bulk-import/"},
        {"name": "Загрузка фото", "url": "/admin/catalog/bulk-images/"},
    ],
    
    # Кастомные ссылки в боковом меню
    "custom_links": {
        "catalog": [{
            "name": "Быстрое добавление",
            "url": "/admin/catalog/quick-add/",
            "icon": "fas fa-bolt",
        }, {
            "name": "Массовый импорт",
            "url": "/admin/catalog/bulk-import/",
            "icon": "fas fa-file-import",
        }, {
            "name": "Загрузка фото",
            "url": "/admin/catalog/bulk-images/",
            "icon": "fas fa-images",
        }],
        "partners": [{
            "name": "Массовый импорт товаров",
            "url": "/admin/partners/bulk-import/",
            "icon": "fas fa-file-import",
        }]
    },
    
    #############
    # Side Menu #
    #############
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    
    # Порядок приложений в меню
    "order_with_respect_to": [
        "catalog",
        "auth",
    ],
    
    # Иконки для моделей (Font Awesome)
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "catalog.Category": "fas fa-folder",
        "catalog.Product": "fas fa-cube",
        "catalog.ProductImage": "fas fa-images",
        "catalog.Brand": "fas fa-tag",
        "catalog.ImportLog": "fas fa-file-import",
        "core.Page": "fas fa-file-alt",
        "orders.Order": "fas fa-shopping-cart",
        "partners.PartnerRequest": "fas fa-user-plus",
        "partners.Partner": "fas fa-handshake",
        "partners.PartnerSettings": "fas fa-cogs",
    },
    
    # Иконки по умолчанию
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    
    #############
    # UI Tweaks #
    #############
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    
    # Показывать UI настройки
    "show_ui_builder": False,
    
    ###############
    # Change view #
    ###############
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
}

# Jazzmin UI Tweaks
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",  # Тёмная тема. Другие варианты: default, cosmo, flatly, litera, lumen, minty, pulse, sandstone, simplex, sketchy, slate, solar, spacelab, superhero, united, yeti
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}
