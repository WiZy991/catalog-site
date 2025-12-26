from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q, Min, Max
from django.core.paginator import Paginator
from django.conf import settings
from .models import Category, Product
from .filters import ProductFilter, get_brand_choices


class CatalogView(ListView):
    """Главная страница каталога."""
    model = Category
    template_name = 'catalog/catalog.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(parent=None, is_active=True).order_by('order', 'name').prefetch_related('children')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем подкатегории для каждой категории
        for category in context['categories']:
            category.active_children = category.children.filter(is_active=True)
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
        descendants = self.category.get_descendants(include_self=True)
        queryset = Product.objects.filter(
            category__in=descendants,
            is_active=True
        ).select_related('category').prefetch_related('images')
        
        # Применяем фильтры
        self.filterset = ProductFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['breadcrumbs'] = self.category.get_ancestors(include_self=True)
        # Получаем подкатегории через related_name 'children'
        context['subcategories'] = self.category.children.filter(is_active=True).order_by('order', 'name')
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
            is_active=True
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
                            is_active=True
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
                is_active=True
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
            context['subcategories'] = self.category.children.filter(is_active=True).order_by('order', 'name')
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
                is_active=True
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
        return Product.objects.filter(is_active=True).select_related('category').prefetch_related('images')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        
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
                
                # Извлекаем коды моделей из применимости (например, "NHW20" из "NHW20 F/R" или "FZ380" из "FZ380/HZ380")
                def extract_model_codes(applicability_items):
                    """Извлекает коды моделей из элементов применимости."""
                    model_codes = set()
                    for item in applicability_items:
                        item_clean = item.strip()
                        if not item_clean:
                            continue
                        
                        # Ищем коды моделей - обычно это буквы+цифры в начале строки (например, NHW20, FZ380, LC80)
                        # Паттерн: одна или несколько букв, затем цифры (минимум 2 цифры для кода модели)
                        model_matches = re.findall(r'\b([A-Z]{1,4}\d{2,})\b', item_clean, re.IGNORECASE)
                        for code in model_matches:
                            model_codes.add(code.upper())
                        
                        # Также добавляем полную строку (нормализованную) для случаев, когда код модели - это вся строка
                        item_normalized = re.sub(r'\s+', ' ', item_clean).upper().strip()
                        if item_normalized:
                            model_codes.add(item_normalized)
                    
                    return model_codes
                
                # Извлекаем коды моделей текущего товара
                product_model_codes = extract_model_codes(product_applicability_list)
                
                if product_model_codes:
                    # Получаем ВСЕ активные товары с применимостью (кроме текущего)
                    all_candidates = list(Product.objects.filter(
                        is_active=True,
                        applicability__isnull=False
                    ).exclude(
                        pk=product.pk,
                        applicability=''
                    ).select_related('category').prefetch_related('images')[:200])
                    
                    # Точная проверка пересечения кодов моделей
                    matching_products = []
                    
                    for candidate_product in all_candidates:
                        if not candidate_product.applicability:
                            continue
                        
                        # Извлекаем коды моделей кандидата
                        candidate_applicability_list = candidate_product.get_applicability_list()
                        candidate_model_codes = extract_model_codes(candidate_applicability_list)
                        
                        # Проверяем пересечение кодов моделей
                        # Товар попадает в подборку только если есть хотя бы один общий код модели
                        if product_model_codes & candidate_model_codes:  # Пересечение множеств
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
                is_active=True
            ).exclude(pk=product.pk).select_related('category').prefetch_related('images')[:12]
        
        # Приоритет 3: Если не нашли, ищем товары того же бренда в дочерних категориях
        if not related_products.exists() and product.brand and product.category:
            brand_normalized = product.brand.strip()
            descendants = product.category.get_descendants(include_self=True)
            related_products = Product.objects.filter(
                brand__iexact=brand_normalized,
                category__in=descendants,
                is_active=True
            ).exclude(pk=product.pk).select_related('category').prefetch_related('images')[:12]
        
        # Приоритет 4: Если не нашли, берем из той же категории (только если нет бренда)
        if not related_products.exists() and product.category and not product.brand:
            related_products = Product.objects.filter(
                category=product.category,
                is_active=True
            ).exclude(pk=product.pk).select_related('category').prefetch_related('images')[:12]
        
        context['related_products'] = related_products[:6]  # Показываем максимум 6
        context['images'] = product.images.all()
        context['characteristics'] = product.get_characteristics_list()
        context['cross_numbers'] = product.get_cross_numbers_list()
        context['applicability'] = product.get_applicability_list()
        
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
            is_active=True
        )
    else:
        queryset = Product.objects.filter(is_active=True)
    
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
    """Поиск товаров."""
    query = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)
    
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(article__icontains=query) |
            Q(brand__icontains=query) |
            Q(cross_numbers__icontains=query) |
            Q(applicability__icontains=query),
            is_active=True
        ).select_related('category').prefetch_related('images')
    else:
        products = Product.objects.none()
    
    paginator = Paginator(products, getattr(settings, 'PRODUCTS_PER_PAGE', 24))
    products_page = paginator.get_page(page)
    
    return render(request, 'catalog/search.html', {
        'query': query,
        'products': products_page,
        'paginator': paginator,
    })

