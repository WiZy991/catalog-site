from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.http import JsonResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.db.models import Q, Min, Max
from django.core.paginator import Paginator
from django.urls import reverse
from django.conf import settings
from .models import Category, Product
from .filters import ProductFilter, get_brand_choices
from .services import format_models_multiline


class CatalogView(ListView):
    """Главная страница каталога."""
    model = Category
    template_name = 'catalog/catalog.html'
    context_object_name = 'categories'

    def get_queryset(self):
        # Показываем все активные корневые категории, отсортированные по order
        return Category.objects.filter(
            parent=None,
            is_active=True
        ).order_by('order', 'name').prefetch_related('children')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Фильтруем категории, у которых есть товары (включая подкатегории)
        categories_with_products = []
        for category in context['categories']:
            category.active_children = category.children.filter(is_active=True)
            # Проверяем, есть ли товары в категории или её подкатегориях (только retail)
            descendants = category.get_descendants(include_self=True)
            # Преобразуем QuerySet в список ID для более надежной работы
            descendant_ids = list(descendants.values_list('id', flat=True))
            if descendant_ids:
                product_count = Product.objects.filter(
                    category_id__in=descendant_ids,
                    is_active=True,
                    catalog_type='retail',
                    quantity__gt=0  # Только товары с количеством больше 0
                ).count()
            else:
                product_count = 0
            if product_count > 0:
                category.retail_product_count = product_count
                categories_with_products.append(category)
        
        context['categories'] = categories_with_products
        return context


class CategoryView(ListView):
    """Страница категории с товарами."""
    model = Product
    template_name = 'catalog/category.html'
    context_object_name = 'products'
    paginate_by = None

    def get_category(self):
        path = self.kwargs.get('path', '')
        if not path:
            return None
        
        slugs = [s for s in path.split('/') if s]  # Убираем пустые строки
        
        if not slugs:
            return None
        
        
        category = None
        for slug in slugs:
            if category:
                category = get_object_or_404(
                    Category, 
                    slug=slug, 
                    parent=category,
                    is_active=True
                )
            else:
                category = get_object_or_404(
                    Category, 
                    slug=slug, 
                    parent=None,
                    is_active=True
                )
        return category
    

    def get_queryset(self):
        self.category = self.get_category()
        if not self.category:
            # Если категория не найдена, возвращаем пустой queryset
            # Это вызовет 404 через get_object_or_404 в get_category
            from django.core.exceptions import Http404
            raise Http404("Категория не найдена")
        
        descendants = self.category.get_descendants(include_self=True)
        queryset = Product.objects.filter(
            category__in=descendants,
            is_active=True,
            catalog_type='retail',  # Только товары из основного каталога
            quantity__gt=0  # Только товары с количеством больше 0
        ).filter(
            Q(availability='in_stock') | Q(availability='order')  # Товары в наличии или под заказ
        ).select_related('category').prefetch_related('images')
        
        # Применяем фильтры
        self.filterset = ProductFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.category:
            from django.core.exceptions import Http404
            raise Http404("Категория не найдена")
        
        context['category'] = self.category
        context['breadcrumbs'] = self.category.get_ancestors(include_self=True)
        # Получаем подкатегории через related_name 'children'
        context['subcategories'] = self.category.children.filter(is_active=True).order_by('name')
        context['filter'] = self.filterset
        
        # Пагинация
        products = self.get_queryset()
        paginator = Paginator(products, getattr(settings, 'PRODUCTS_PER_PAGE', 24))
        page = self.request.GET.get('page', 1)
        context['products'] = paginator.get_page(page)
        context['paginator'] = paginator
        
        # Данные для фильтров
        all_products = Product.objects.filter(
            category__in=self.category.get_descendants(include_self=True),
            is_active=True,
            catalog_type='retail',  # Только товары из основного каталога
            quantity__gt=0  # Только товары с количеством больше 0
        )
        context['brands'] = get_brand_choices(self.category)
        context['price_range'] = all_products.aggregate(min_price=Min('price'), max_price=Max('price'))
        
        return context


class CatalogItemView(ListView):
    """Универсальный view для категорий и товаров."""
    model = Product
    template_name = 'catalog/category.html'
    context_object_name = 'products'
    paginate_by = None
    
    def dispatch(self, request, *args, **kwargs):
        """Определяем, что это - категория или товар."""
        category_path = kwargs.get('category_path', '')
        slug = kwargs.get('slug', '')
        
        if category_path and slug:
            category_slugs = [s for s in category_path.split('/') if s]
            parent_category = None
            
            # Пытаемся найти родительскую категорию
            try:
                for cat_slug in category_slugs:
                    if parent_category:
                        parent_category = Category.objects.get(slug=cat_slug, parent=parent_category, is_active=True)
                    else:
                        parent_category = Category.objects.get(slug=cat_slug, parent=None, is_active=True)
                
                # Если нашли родительскую категорию, проверяем, не является ли slug тоже категорией
                if parent_category:
                    try:
                        subcategory = Category.objects.get(slug=slug, parent=parent_category, is_active=True)
                        # Если это категория, обрабатываем как категорию
                        self.is_category = True
                        self.category = subcategory
                        return super().dispatch(request, *args, **kwargs)
                    except Category.DoesNotExist:
                        # Это не категория, проверяем, является ли это товаром
                        descendants = parent_category.get_descendants(include_self=True)
                        product = Product.objects.filter(
                            slug=slug,
                            category__in=descendants,
                            is_active=True,
                            quantity__gt=0  # Только товары с количеством больше 0
                        ).filter(
                            Q(availability='in_stock') | Q(availability='order')  # Товары в наличии или под заказ
                        ).first()
                        
                        if product:
                            # Это товар - используем ProductView напрямую
                            product_view = ProductView()
                            product_view.request = request
                            product_view.args = args
                            product_view.kwargs = kwargs
                            return product_view.dispatch(request, *args, **kwargs)
                        else:
                            # Ни категория, ни товар - 404
                            from django.http import Http404
                            raise Http404("Не найдено")
            except Category.DoesNotExist:
                pass
        
        # Если не определили, пробуем как товар
        product_view = ProductView()
        product_view.request = request
        product_view.args = args
        product_view.kwargs = kwargs
        return product_view.dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Если это категория, используем логику CategoryView
        if hasattr(self, 'is_category') and self.is_category:
            category = self.category
            descendants = category.get_descendants(include_self=True)
            queryset = Product.objects.filter(
                category__in=descendants,
                is_active=True,
                catalog_type='retail',  # Только товары из основного каталога
                quantity__gt=0  # Только товары с количеством больше 0
            ).filter(
                Q(availability='in_stock') | Q(availability='order')  # Товары в наличии или под заказ
            ).select_related('category').prefetch_related('images')
            
            # Применяем фильтры
            self.filterset = ProductFilter(self.request.GET, queryset=queryset)
            return self.filterset.qs
        else:
            # Это не категория, возвращаем пустой queryset (не должно доходить сюда)
            return Product.objects.none()
    
    def get_context_data(self, **kwargs):
        # Если это категория, используем логику CategoryView
        if hasattr(self, 'is_category') and self.is_category:
            context = super().get_context_data(**kwargs)
            context['category'] = self.category
            context['breadcrumbs'] = self.category.get_ancestors(include_self=True)
            context['subcategories'] = self.category.children.filter(is_active=True).order_by('name')
            context['filter'] = self.filterset
            
            # Пагинация
            products = self.get_queryset()
            paginator = Paginator(products, getattr(settings, 'PRODUCTS_PER_PAGE', 24))
            page = self.request.GET.get('page', 1)
            context['products'] = paginator.get_page(page)
            context['paginator'] = paginator
            
            # Данные для фильтров
            all_products = Product.objects.filter(
                category__in=self.category.get_descendants(include_self=True),
                is_active=True,
                catalog_type='retail',  # Только товары из основного каталога
                quantity__gt=0  # Только товары с количеством больше 0
            )
            context['brands'] = get_brand_choices(self.category)
            context['price_range'] = all_products.aggregate(min_price=Min('price'), max_price=Max('price'))
            
            return context
        else:
            # Это не категория, возвращаем пустой контекст (не должно доходить сюда)
            return super().get_context_data(**kwargs)
    


class ProductView(DetailView):
    """Страница товара."""
    model = Product
    template_name = 'catalog/product.html'
    context_object_name = 'product'
    
    def dispatch(self, request, *args, **kwargs):
        """Проверяем, не является ли это категорией."""
        category_path = kwargs.get('category_path', '')
        slug = kwargs.get('slug', '')
        
        # Проверяем, не является ли это категорией
        if category_path and slug:
            category_slugs = [s for s in category_path.split('/') if s]
            parent_category = None
            
            # Пытаемся найти родительскую категорию
            try:
                for cat_slug in category_slugs:
                    if parent_category:
                        parent_category = Category.objects.get(slug=cat_slug, parent=parent_category, is_active=True)
                    else:
                        parent_category = Category.objects.get(slug=cat_slug, parent=None, is_active=True)
                
                # Если нашли родительскую категорию, проверяем, не является ли slug тоже категорией
                if parent_category:
                    try:
                        subcategory = Category.objects.get(slug=slug, parent=parent_category, is_active=True)
                        # Если это категория, поднимаем 404, чтобы Django попробовал CategoryView
                        from django.http import Http404
                        raise Http404("Это категория, а не товар")
                    except Category.DoesNotExist:
                        pass
            except Category.DoesNotExist:
                pass
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self, queryset=None):
        """Получает товар."""
        if queryset is None:
            queryset = self.get_queryset()
        
        category_path = self.kwargs.get('category_path', '')
        slug = self.kwargs.get('slug', '')
        
        # Ищем товар
        if category_path:
            # Пытаемся найти категорию для товара
            category_slugs = category_path.split('/')
            parent_category = None
            for cat_slug in category_slugs:
                if parent_category:
                    try:
                        parent_category = Category.objects.get(slug=cat_slug, parent=parent_category, is_active=True)
                    except Category.DoesNotExist:
                        parent_category = None
                        break
                else:
                    try:
                        parent_category = Category.objects.get(slug=cat_slug, parent=None, is_active=True)
                    except Category.DoesNotExist:
                        parent_category = None
                        break
            
            if parent_category:
                # Ищем товар в этой категории или её потомках
                descendants = parent_category.get_descendants(include_self=True)
                obj = get_object_or_404(queryset, slug=slug, category__in=descendants)
            else:
                obj = get_object_or_404(queryset, slug=slug)
        else:
            # Если не нашли по категории, ищем просто по slug
            obj = get_object_or_404(queryset, slug=slug)
        
        # Увеличиваем счётчик просмотров
        Product.objects.filter(pk=obj.pk).update(views_count=obj.views_count + 1)
        
        return obj
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        # ВАЖНО: Фильтруем товары так же, как в каталоге - только активные с количеством > 0 и в наличии
        # Это гарантирует, что если товар показывается в каталоге, он будет доступен и на странице товара
        return Product.objects.filter(
            is_active=True,
            catalog_type='retail',  # Только товары из основного каталога
            quantity__gt=0  # Только товары с количеством больше 0
        ).filter(
            Q(availability='in_stock') | Q(availability='order')  # Товары в наличии или под заказ
        ).select_related('category').prefetch_related('images')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        def _format_models_multiline(v: str) -> str:
            return format_models_multiline(v)
        
        if product.category:
            context['breadcrumbs'] = product.category.get_ancestors(include_self=True)
        
        # Похожие товары - подборка по автомобилю из применимости
        related_products = Product.objects.none()
        
        # Приоритет 1: ВСЕ товары для того же автомобиля (из применимости) - любой бренд, любая категория
        # Например, если товар для "Prius NHW20", показываем все товары для "Prius NHW20"
        if product.applicability:
            product_applicability_list = product.get_applicability_list()
            if product_applicability_list:
                import re
                
                # Извлекаем коды моделей и применимость из элементов применимости
                def extract_model_codes(applicability_items):
                    """Извлекает коды моделей и применимость из элементов применимости."""
                    model_codes = set()
                    applicability_strings = set()
                    
                    for item in applicability_items:
                        item_clean = item.strip()
                        if not item_clean:
                            continue
                        
                        # Добавляем полную строку применимости (нормализованную)
                        item_normalized = re.sub(r'\s+', ' ', item_clean).upper().strip()
                        if item_normalized:
                            applicability_strings.add(item_normalized)
                        
                        # Ищем коды моделей - обычно это буквы+цифры (например, NHW20, FZ380, LC80, 2GR)
                        # Паттерн: буквы+цифры или цифры+буквы (например, 2GR, 1NZ, 3RZ)
                        # Также ищем стандартные коды: 1-4 буквы + 2+ цифры
                        model_matches = re.findall(r'\b([A-Z]{1,4}\d{2,}|\d{1,2}[A-Z]{1,3}[#]?)\b', item_clean, re.IGNORECASE)
                        for code in model_matches:
                            # Убираем символ # в конце для сравнения
                            code_clean = code.upper().rstrip('#')
                            if len(code_clean) >= 2:  # Минимум 2 символа для кода
                                model_codes.add(code_clean)
                        
                        # Также ищем отдельные коды моделей в строке (например, "2GR#" из "2GR#")
                        # Извлекаем все возможные коды моделей
                        all_codes = re.findall(r'\b([A-Z0-9#]{2,6})\b', item_clean, re.IGNORECASE)
                        for code in all_codes:
                            code_clean = code.upper().rstrip('#')
                            # Проверяем, что это похоже на код модели (содержит и буквы, и цифры, или короткий код)
                            if (re.search(r'[A-Z]', code_clean) and re.search(r'\d', code_clean)) or len(code_clean) <= 4:
                                if len(code_clean) >= 2:
                                    model_codes.add(code_clean)
                    
                    return model_codes, applicability_strings
                
                # Извлекаем коды моделей и применимость текущего товара
                product_model_codes, product_applicability_strings = extract_model_codes(product_applicability_list)
                
                if product_model_codes or product_applicability_strings:
                    # Получаем ВСЕ активные товары с применимостью (кроме текущего)
                    # ВАЖНО: не ограничиваемся категорией, чтобы показать все товары для этой машины
                    all_candidates = list(Product.objects.filter(
                        is_active=True,
                        catalog_type='retail',  # Только товары из основного каталога
                        applicability__isnull=False
                    ).exclude(
                        pk=product.pk,
                        applicability=''
                    ).select_related('category').prefetch_related('images')[:300])
                    
                    # Точная проверка пересечения кодов моделей и применимости
                    matching_products = []
                    
                    for candidate_product in all_candidates:
                        if not candidate_product.applicability:
                            continue
                        
                        # Извлекаем коды моделей и применимость кандидата
                        candidate_applicability_list = candidate_product.get_applicability_list()
                        candidate_model_codes, candidate_applicability_strings = extract_model_codes(candidate_applicability_list)
                        
                        # Проверяем пересечение:
                        # 1. Точное совпадение кодов моделей
                        # 2. Или точное совпадение строк применимости
                        model_match = product_model_codes & candidate_model_codes
                        applicability_match = product_applicability_strings & candidate_applicability_strings
                        
                        # Товар попадает в подборку только если есть точное совпадение
                        if model_match or applicability_match:
                            matching_products.append(candidate_product)
                        
                        # Ограничиваем количество результатов
                        if len(matching_products) >= 12:
                            break
                    
                    # Преобразуем в queryset
                    if matching_products:
                        product_ids = [p.pk for p in matching_products if p.pk != product.pk]
                        if product_ids:
                            related_products = Product.objects.filter(
                                pk__in=product_ids
                            ).exclude(pk=product.pk).select_related('category').prefetch_related('images')
        
        # Приоритет 2: Если не нашли по применимости, ищем товары того же бренда в той же категории
        if not related_products.exists() and product.brand and product.category:
            brand_normalized = product.brand.strip()
            related_products = Product.objects.filter(
                brand__iexact=brand_normalized,
                category=product.category,
                is_active=True,
                catalog_type='retail'  # Только товары из основного каталога
            ).exclude(pk=product.pk).select_related('category').prefetch_related('images')[:12]
        
        # Приоритет 3: Если не нашли, ищем товары того же бренда в дочерних категориях
        if not related_products.exists() and product.brand and product.category:
            brand_normalized = product.brand.strip()
            descendants = product.category.get_descendants(include_self=True)
            related_products = Product.objects.filter(
                brand__iexact=brand_normalized,
                category__in=descendants,
                is_active=True,
                catalog_type='retail'  # Только товары из основного каталога
            ).exclude(pk=product.pk).select_related('category').prefetch_related('images')[:12]
        
        # Приоритет 4: Если не нашли, берем из той же категории (только если нет бренда)
        if not related_products.exists() and product.category and not product.brand:
            related_products = Product.objects.filter(
                category=product.category,
                is_active=True,
                catalog_type='retail'  # Только товары из основного каталога
            ).exclude(pk=product.pk).select_related('category').prefetch_related('images')[:12]
        
        context['related_products'] = related_products[:6]  # Показываем максимум 6
        context['images'] = product.images.all()
        
        # Получаем характеристики и фильтруем ненужные
        all_characteristics = product.get_characteristics_list()
        article2_value = ''
        # OEM в верхней строке показываем из cross_numbers (если есть),
        # чтобы не терять несколько OEM-номеров.
        cross_numbers = product.get_cross_numbers_list()
        if cross_numbers:
            article2_value = ', '.join(cross_numbers)
        article2_keys = ('артикул2', 'article2', 'oem', 'oem номер', 'oem-номер')
        if not article2_value:
            for key, value in all_characteristics:
                key_lower = str(key).lower().strip()
                if key_lower in article2_keys and value:
                    article2_value = str(value).strip()
                    break

        # Fallback: если Артикул2/OEM не пришёл в характеристиках,
        # иногда OEM хранится внутри наименования как "12345-67890".
        if not article2_value:
            import re
            name = str(product.name or '')
            m = re.search(r'\b\d{4,6}-\d{4,6}\b', name)
            if m:
                article2_value = m.group(0)

        # Если Артикул2 в 1С приходит как "/022248" (т.е. не похоже на полный OEM),
        # подставляем "полный" OEM вида "90947-02247" из названия.
        if article2_value:
            import re
            full_oem = re.search(r'\b\d{4,6}-\d{4,6}\b', str(product.name or ''))
            if str(article2_value).strip().startswith('/') and full_oem:
                article2_value = full_oem.group(0)
        if article2_value:
            article2_value = str(article2_value).strip().lstrip('/')
        # Исключаем материалы и другие ненужные характеристики
        excluded_keys = ['прокладка', 'gasket', 'паронит', 'paronit', 'материал', 'material']
        characteristics = []
        first_model = ''
        first_engine = ''
        first_characteristic = ''
        has_size_in_source = False
        has_oem_row = False
        note_value = ''
        for key, value in all_characteristics:
            key_lower = key.lower().strip()
            # Пропускаем материалы и другие ненужные характеристики
            if not any(excluded in key_lower for excluded in excluded_keys):
                # В блоке характеристик Артикул2 показываем как OEM.
                if key_lower in article2_keys and product.article:
                    oem_value = article2_value or str(value).strip().lstrip('/')
                    if oem_value:
                        characteristics.append(('OEM', oem_value))
                        has_oem_row = True
                elif ('размер' in key_lower) or ('size' in key_lower):
                    has_size_in_source = True
                    # Иногда 1С ошибочно кладёт код двигателя в поле "Размер" (например: "3VZ/5VZ").
                    v = str(value).strip()
                    v_lower = v.lower()
                    size_parts = [p.strip() for p in v.split('/') if p.strip()]
                    is_single_letter_size = bool(size_parts) and all(len(p) == 1 for p in size_parts)
                    # Признак кода двигателя:
                    # - обычно есть "/" (например: "1ARFE/2ZRFE", "EW/EV")
                    # - либо есть буквы+цифры (например: "F23A")
                    # Cross-номер/прочее обычно содержит "-" (мы его ниже не рассматриваем).
                    # ВАЖНО: значения вроде "12V/1.2KW/9T/ПР/ОТК" нельзя считать кодом двигателя.
                    contains_characteristic_markers = (
                        '.' in v
                        or 'kw' in v_lower
                        or 'квт' in v_lower
                        or 'пр' in v_lower
                        or 'отк' in v_lower
                    )
                    is_engine_code = (
                        ('/' in v and bool(re.search(r'[A-Za-zА-Яа-я]', v)))
                        or (bool(re.search(r'[A-Za-zА-Яа-я]', v)) and bool(re.search(r'\d', v)))
                    ) and ('-' not in v) and (not v.strip().startswith('/')) and (not contains_characteristic_markers) and (not is_single_letter_size)
                    if is_engine_code:
                        characteristics.append(('Применимо для двигателей', v))
                        if not first_engine:
                            first_engine = v
                    else:
                        # Значения вида "R/R/L" — это размер/сторона, а не двигатель.
                        if is_single_letter_size:
                            characteristics.append(('Характеристика', v))
                            if not first_characteristic:
                                first_characteristic = v
                        else:
                            characteristics.append(('Характеристика', v))
                            if not first_characteristic:
                                first_characteristic = v
                elif key_lower in ('примечание', 'note'):
                    # В карточке вместо "Примечание" показываем как "Кросс-номер".
                    note_value = str(value).strip()
                    if note_value:
                        characteristics.append(('Кросс-номера', note_value))
                else:
                    out_key = key
                    if key_lower in ('кузов', 'body'):
                        out_key = 'Применимо для моделей'
                        value = _format_models_multiline(value)
                        if not first_model:
                            first_model = str(value).strip()
                    elif 'применимо для моделей' in key_lower:
                        out_key = 'Применимо для моделей'
                        value = _format_models_multiline(value)
                        if not first_model:
                            first_model = str(value).strip()
                    elif key_lower in ('двигатель', 'engine'):
                        out_key = 'Применимо для двигателей'
                        if not first_engine:
                            first_engine = str(value).strip()
                    elif key_lower in ('кросс-номер', 'кросс номер'):
                        out_key = 'Кросс-номера'
                    characteristics.append((out_key, value))

        if article2_value and not has_oem_row:
            characteristics.append(('OEM', article2_value))

        # Fallback: если "Размер" или "Двигатель" не пришли из XML,
        # пытаемся извлечь их из названия товара (последние сегменты после запятых).
        import re
        existing_keys = {str(k).strip().lower() for k, _ in characteristics}
        name_parts = [p.strip() for p in (product.name or '').split(',') if p and p.strip()]

        if name_parts and not has_size_in_source:
            size_candidate = name_parts[-1]
            if size_candidate:
                import re
                # Fallback: размер в названии часто стоит сразу после кода двигателя,
                # поэтому пробуем взять "следующий сегмент после двигателя".
                def _looks_like_engine_code(s: str) -> bool:
                    s = str(s or '').strip()
                    if not s:
                        return False
                    return bool(re.search(r'[A-Za-zА-Яа-я]', s)) and bool(re.search(r'\d', s))

                engine_idx = None
                # Ищем ПОСЛЕДНИЙ сегмент, который похож на код двигателя,
                # чтобы брать размер именно после "самого позднего" двигателя в названии.
                for i in range(len(name_parts) - 1, -1, -1):
                    if _looks_like_engine_code(name_parts[i]):
                        engine_idx = i
                        break
                if engine_idx is not None and engine_idx + 1 < len(name_parts):
                    size_candidate = name_parts[engine_idx + 1]

                s = str(size_candidate).strip()
                if s and ('/' not in s) and (not _looks_like_engine_code(s)):
                    characteristics.append(('Характеристики', s))

        if name_parts and 'двигатель' not in existing_keys and 'engine' not in existing_keys and 'применимо для двигателей' not in existing_keys:
            def _looks_like_engine_token(s: str) -> bool:
                s = str(s or '').strip()
                if not s:
                    return False
                # Cross-номер содержит "-"
                if '-' in s:
                    return False
                sl = s.lower()
                if '.' in s or 'kw' in sl or 'квт' in sl or 'пр' in sl or 'отк' in sl:
                    return False
                # Варианты вида "/022248" не берем как двигатель
                if s.startswith('/'):
                    return False
                # Двигатель — это либо "буквы+цифры", либо коды типа "EW/EV" (есть "/",
                # но цифр может не быть). Не принимаем cross-номера с "-" и значения вида "/022248".
                # Варианты вида "R/R/L" (односимвольные сегменты) считаем характеристикой, а не двигателем.
                has_letters = bool(re.search(r'[A-Za-zА-Яа-я]', s))
                has_digits = bool(re.search(r'\d', s))
                if '/' in s and has_letters and '-' not in s and not s.startswith('/'):
                    parts = [p for p in s.split('/') if p]
                    # Если во всех частях по 1 символу (например, R/R/L), это НЕ двигатель.
                    if parts and all(len(p.strip()) <= 1 for p in parts):
                        return False
                    return True
                return has_letters and has_digits and '-' not in s

            for part in reversed(name_parts):
                if _looks_like_engine_token(part):
                    characteristics.append(('Применимо для двигателей', part))
                    if not first_engine:
                        first_engine = part
                    break

        # Fallback для "Кузов": часто "Кузов" не проходит фильтрацию в characteristics,
        # но остаётся в applicability. Если кузов не найден — пытаемся взять
        # из applicability, исключив значение двигателя.
        existing_char_keys = {str(k).strip().lower() for k, _ in characteristics}
        has_body = any(k in existing_char_keys for k in ('кузов', 'body', 'применимо для моделей'))
        if not has_body:
            engine_val = ''
            for k, v in characteristics:
                if str(k).strip().lower() in ('двигатель', 'engine'):
                    engine_val = str(v).strip()
                    break

            applicability_list = product.get_applicability_list()
            if applicability_list:
                for item in applicability_list:
                    item_str = str(item).strip()
                    if not item_str:
                        continue
                    if engine_val and item_str == engine_val:
                        continue
                    if item_str.startswith('/'):
                        continue
                    if '-' in item_str:
                        continue
                    # Должно быть похоже на код с буквами и цифрами.
                    if re.search(r'[A-Za-zА-Яа-я]', item_str) and re.search(r'\d', item_str):
                        characteristics.append(('Применимо для моделей', item_str))
                        if not first_model:
                            first_model = item_str
                        break

        # Удаляем дубли: если "Кузов" и "Двигатель" содержат одинаковое значение,
        # оставляем только "Кузов" (для подобных кейсов с кодами кузова).
        body_values = {
            ' '.join(str(v).strip().lower().split())
            for k, v in characteristics
            if str(k).strip().lower() in ('кузов', 'body') and str(v).strip()
        }
        if body_values:
            cleaned_characteristics = []
            for k, v in characteristics:
                k_norm = str(k).strip().lower()
                v_norm = ' '.join(str(v).strip().lower().split())
                if k_norm in ('двигатель', 'engine', 'применимо для двигателей') and v_norm in body_values:
                    continue
                cleaned_characteristics.append((k, v))
            characteristics = cleaned_characteristics

        # Убираем полные дубли строк (одинаковый ключ + значение).
        unique_characteristics = []
        seen_pairs = set()
        for k, v in characteristics:
            pair = (str(k).strip().lower(), ' '.join(str(v).strip().lower().split()))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            unique_characteristics.append((k, v))
        characteristics = unique_characteristics
        
        # Добавляем вольтаж, если он есть в применимости
        voltage = product.get_voltage_from_applicability()
        if voltage:
            # Проверяем, нет ли уже вольтажа в характеристиках
            has_voltage = any(key.lower() in ['вольтаж', 'voltage', 'напряжение'] for key, _ in characteristics)
            if not has_voltage:
                characteristics.append(('Напряжение', voltage))
        
        context['characteristics'] = characteristics

        # Для h1 убираем хвост с кросс-номерами, чтобы не дублировать блок "Кросс-номер" ниже.
        display_name = str(product.name or '')
        cross_values = []
        if product.cross_numbers:
            cross_values.extend([x.strip() for x in str(product.cross_numbers).replace('\n', ',').split(',') if x.strip()])
        if note_value:
            cross_values.extend([x.strip() for x in str(note_value).replace('\n', ',').split(',') if x.strip()])
        # Убираем дубли, сохраняя порядок
        uniq_cross = []
        seen_cross = set()
        for x in cross_values:
            xl = x.lower()
            if xl not in seen_cross:
                seen_cross.add(xl)
                uniq_cross.append(x)
        # Вырезаем найденные кросс-номера из названия
        for x in uniq_cross:
            escaped = re.escape(x)
            display_name = re.sub(rf'(?:,\s*)?{escaped}(?:\s*,)?', ', ', display_name, flags=re.IGNORECASE)
        # Дополнительно удаляем "обрезки"/остатки кросс-номеров в сегментах названия
        # (например, "48531-B1"), если они выглядят как номер с дефисом.
        cleaned_parts = []
        for part in [p.strip() for p in display_name.split(',') if p and p.strip()]:
            p = str(part).strip()
            looks_like_cross = ('-' in p) and bool(re.search(r'\d', p))
            if looks_like_cross:
                continue
            cleaned_parts.append(p)
        display_name = ', '.join(cleaned_parts)
        # Чистим повторные запятые/пробелы после вырезания
        display_name = re.sub(r',\s*,+', ', ', display_name)
        display_name = re.sub(r'\s+,', ',', display_name)
        display_name = re.sub(r',\s*$', '', display_name).strip()
        # Заголовок для карточек: тип, номер, OEM, 1 модель, 1 двигатель, 1 характеристика.
        title_base = ''
        def _first_model_and_body(raw: str) -> str:
            text = str(raw or '').replace('\n', ' ').strip()
            if not text:
                return ''
            parts = [p.strip() for p in text.split(',') if p and p.strip()]
            if not parts:
                return ''
            # Для заголовка оставляем только первую модель и первый кузов.
            if len(parts) >= 2:
                return f'{parts[0]}, {parts[1]}'
            return parts[0]

        def _first_engine(raw: str) -> str:
            text = str(raw or '').replace('\n', ' ').strip()
            if not text:
                return ''
            # Берем только первый двигатель из списков "A/B, C" и т.п.
            text = text.split(',')[0].strip()
            text = text.split('/')[0].strip()
            return text

        name_parts = [p.strip() for p in str(display_name or '').split(',') if p and p.strip()]
        if name_parts:
            title_base = name_parts[0]
        compact_model = _first_model_and_body(first_model)
        compact_engine = _first_engine(first_engine)
        title_chunks = [x for x in [title_base, product.article or '', article2_value or '', compact_model, compact_engine, first_characteristic] if x]
        unified_title = ', '.join(title_chunks) if title_chunks else display_name
        context['display_name'] = unified_title
        context['cross_numbers'] = product.get_cross_numbers_list()
        context['applicability'] = product.get_applicability_list()
        context['article2_value'] = article2_value
        
        return context


def filter_products_ajax(request):
    """AJAX фильтрация товаров."""
    category_slug = request.GET.get('category')
    page = request.GET.get('page', 1)
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        descendants = category.get_descendants(include_self=True)
        queryset = Product.objects.filter(
            category__in=descendants,
            is_active=True,
            catalog_type='retail',  # Только товары из основного каталога
            quantity__gt=0  # Только товары с количеством больше 0
        ).filter(
            Q(availability='in_stock') | Q(availability='order')  # Товары в наличии или под заказ
        )
    else:
        queryset = Product.objects.filter(
            is_active=True,
            catalog_type='retail',  # Только товары из основного каталога
            quantity__gt=0  # Только товары с количеством больше 0
        ).filter(
            Q(availability='in_stock') | Q(availability='order')  # Товары в наличии или под заказ
        )
    
    # Применяем фильтры
    filterset = ProductFilter(request.GET, queryset=queryset)
    products = filterset.qs.select_related('category').prefetch_related('images')
    
    # Пагинация
    paginator = Paginator(products, getattr(settings, 'PRODUCTS_PER_PAGE', 24))
    products_page = paginator.get_page(page)
    
    # Рендерим HTML
    html = render_to_string('catalog/includes/products_grid.html', {
        'products': products_page,
        'request': request,
    })
    
    pagination_html = render_to_string('catalog/includes/pagination.html', {
        'page_obj': products_page,
        'request': request,
    })
    
    return JsonResponse({
        'html': html,
        'pagination': pagination_html,
        'count': paginator.count,
    })


def search_products(request):
    """Поиск товаров (регистронезависимый, включая кириллицу, по частичным совпадениям слов)."""
    from django.db.models.functions import Lower
    
    query = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)
    
    if query:
        # Разбиваем запрос на отдельные слова (минимум 2 символа)
        query_words = [word.strip() for word in query.split() if len(word.strip()) >= 2]
        
        if not query_words:
            # Если слово слишком короткое, ищем весь запрос целиком
            query_words = [query.strip()]
        
        # Используем комбинацию методов для надежного регистронезависимого поиска
        # Для SQLite лучше использовать iregex, для других БД - icontains
        products = Product.objects.filter(
            is_active=True,
            catalog_type='retail'  # Только товары из основного каталога
        ).filter(
            Q(quantity__gt=0) | Q(availability='order')  # Товары с остатком или под заказ
        )
        
        # Для каждого слова создаём условие поиска
        # Используем AND - товар должен содержать ВСЕ слова из запроса
        for word in query_words:
            word_escaped = word.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').replace('[', '\\[').replace(']', '\\]')
            word_q = (
                # Используем iregex для регистронезависимого поиска (лучше работает с кириллицей в SQLite)
                Q(name__iregex=word_escaped) |
                Q(article__iregex=word_escaped) |
                Q(brand__iregex=word_escaped) |
                Q(cross_numbers__iregex=word_escaped) |
                Q(applicability__iregex=word_escaped) |
                # Резервный вариант с icontains (на случай проблем с regex)
                Q(name__icontains=word) |
                Q(article__icontains=word) |
                Q(brand__icontains=word) |
                Q(cross_numbers__icontains=word) |
                Q(applicability__icontains=word)
            )
            products = products.filter(word_q)
        
        products = products.select_related('category').prefetch_related('images').distinct()
    else:
        products = Product.objects.none()
    
    paginator = Paginator(products, getattr(settings, 'PRODUCTS_PER_PAGE', 24))
    products_page = paginator.get_page(page)
    
    return render(request, 'catalog/search.html', {
        'query': query,
        'products': products_page,
        'paginator': paginator,
    })


def redirect_old_item_url(request, slug):
    """Редирект со старых URL /items/ на новые URL товаров."""
    try:
        # Пытаемся найти товар по slug
        product = Product.objects.get(slug=slug, is_active=True)
        # Редиректим на правильный URL товара
        return HttpResponseRedirect(product.get_absolute_url())
    except Product.DoesNotExist:
        # Если товар не найден, редиректим на каталог
        return HttpResponseRedirect(reverse('catalog:index'))

