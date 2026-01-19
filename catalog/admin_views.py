"""
Дополнительные view для админки каталога.
"""
import csv
import io
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import HttpResponse
import openpyxl
import xlrd

from .forms import BulkImageUploadForm, BulkProductImportForm, QuickProductForm
from .services import (
    process_bulk_images, 
    process_bulk_import, 
    parse_product_name,
    get_or_create_category,
)
from .models import Product, ProductImage


@staff_member_required
def bulk_image_upload(request):
    """Массовая загрузка изображений."""
    if request.method == 'POST':
        form = BulkImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('images')
            create_products = form.cleaned_data['create_products']
            
            # Собираем изображения
            images = []
            for f in files:
                images.append((f.name, f.read()))
            
            # Обрабатываем
            stats = process_bulk_images(images, create_products=create_products)
            
            # Показываем результаты
            messages.success(
                request, 
                f'✅ Загружено изображений: {stats["matched"]} из {stats["total"]}'
            )
            
            if stats['created_products']:
                messages.info(
                    request,
                    f'📦 Создано новых товаров: {stats["created_products"]}'
                )
            
            if stats['not_matched']:
                messages.warning(
                    request,
                    f'⚠️ Не удалось привязать: {stats["not_matched"]} файлов'
                )
                # Показываем список непривязанных
                if stats['not_matched_files'][:10]:
                    files_list = ', '.join(stats['not_matched_files'][:10])
                    if len(stats['not_matched_files']) > 10:
                        files_list += f' и ещё {len(stats["not_matched_files"]) - 10}...'
                    messages.warning(request, f'Файлы: {files_list}')
            
            return redirect('admin:catalog_product_changelist')
    else:
        form = BulkImageUploadForm()
    
    return render(request, 'admin/catalog/bulk_image_upload.html', {
        'form': form,
        'title': 'Массовая загрузка изображений',
    })


@staff_member_required
def bulk_product_import(request):
    """Массовый импорт товаров из файла."""
    if request.method == 'POST':
        form = BulkProductImportForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            auto_category = form.cleaned_data['auto_category']
            auto_brand = form.cleaned_data['auto_brand']
            
            # Читаем файл
            data_rows = []
            filename = file.name.lower()
            
            try:
                if filename.endswith('.csv'):
                    # CSV файл
                    content = file.read().decode('utf-8-sig')
                    reader = csv.DictReader(io.StringIO(content), delimiter=';')
                    for row in reader:
                        # Нормализуем ключи и обрабатываем значения
                        normalized = {}
                        for key, value in row.items():
                            if key:
                                key_normalized = key.lower().strip()
                                # Обрабатываем числовые значения
                                if value and value.strip():
                                    # Пытаемся определить, является ли значение числом
                                    try:
                                        # Убираем пробелы и проверяем формат
                                        value_clean = value.replace(' ', '').replace('\xa0', '').replace(',', '.')
                                        num_value = float(value_clean)
                                        # Если это число, сохраняем и строковое, и числовое значение
                                        normalized[key_normalized] = value.strip()
                                        # Сохраняем числовое значение для цен и остатков
                                        if 'цена' in key_normalized or 'price' in key_normalized:
                                            normalized['price_num'] = num_value
                                        elif 'остаток' in key_normalized or 'quantity' in key_normalized or 'склад' in key_normalized:
                                            normalized['quantity_num'] = int(num_value)
                                            normalized['остаток_num'] = int(num_value)
                                    except (ValueError, TypeError):
                                        # Не число, сохраняем как строку
                                        normalized[key_normalized] = value.strip()
                                else:
                                    normalized[key_normalized] = value.strip() if value else ''
                        data_rows.append(normalized)
                        
                elif filename.endswith(('.xls', '.xlsx')):
                    # Excel файл
                    file.seek(0)  # Сбрасываем позицию файла
                    
                    # Определяем формат файла: старый .xls (бинарный) или новый .xlsx (zip)
                    is_old_xls = filename.endswith('.xls') and not filename.endswith('.xlsx')
                    
                    if is_old_xls:
                        # Старый формат .xls - используем xlrd
                        try:
                            file_content = file.read()
                            wb = xlrd.open_workbook(file_contents=file_content)
                            ws = wb.sheet_by_index(0)
                            
                            # Ищем строку с заголовками
                            header_row_index = 0
                            headers = []
                            
                            # Проверяем первые 15 строк на наличие заголовков
                            for row_num in range(min(15, ws.nrows)):
                                row_values = []
                                for col_num in range(ws.ncols):
                                    cell_value = ws.cell_value(row_num, col_num)
                                    if cell_value:
                                        row_values.append(str(cell_value).strip())
                                    else:
                                        row_values.append('')
                                
                                # Объединяем все значения строки для проверки
                                row_text = ' '.join(row_values).lower()
                                
                                # Проверяем, есть ли в этой строке ключевые слова заголовков
                                header_keywords = ['артикул', 'номенклатура', 'наименование', 'цена', 'остаток', 'склад', 'розничная', 'фарпост']
                                keyword_count = sum(1 for keyword in header_keywords if keyword in row_text)
                                
                                # Если найдено минимум 2 ключевых слова, считаем это строкой заголовков
                                if keyword_count >= 2:
                                    header_row_index = row_num
                                    headers = row_values
                                    break
                            
                            # Если заголовки не найдены, берем первую строку
                            if not headers:
                                headers = [str(ws.cell_value(0, col_num) or '').strip() for col_num in range(ws.ncols)]
                            
                            # Читаем данные начиная со строки после заголовков
                            for row_num in range(header_row_index + 1, ws.nrows):
                                row_data = {}
                                for col_num in range(min(len(headers), ws.ncols)):
                                    if headers[col_num]:
                                        header_key = headers[col_num].lower().strip()
                                        cell = ws.cell(row_num, col_num)
                                        value = cell.value
                                        
                                        # Обрабатываем значение в зависимости от типа
                                        if value is None or value == '':
                                            value = ''
                                        elif cell.ctype == xlrd.XL_CELL_NUMBER:
                                            # Числовое значение
                                            if isinstance(value, float) and value.is_integer():
                                                value_str = str(int(value))
                                            else:
                                                value_str = str(value)
                                            value_str = value_str.replace('.', ',')
                                            row_data[header_key] = value_str
                                            # Сохраняем числовое значение
                                            if 'цена' in header_key or 'price' in header_key:
                                                row_data[header_key + '_num'] = value
                                            elif 'остаток' in header_key or 'quantity' in header_key or 'склад' in header_key:
                                                row_data[header_key + '_num'] = int(value) if isinstance(value, float) and value.is_integer() else int(value)
                                            continue
                                        else:
                                            value = str(value).strip()
                                        
                                        row_data[header_key] = value
                                
                                # Пропускаем полностью пустые строки
                                has_data = any(
                                    str(v).strip() for v in row_data.values() 
                                    if v is not None and str(v).strip() and not str(v).endswith('_num')
                                )
                                if has_data:
                                    data_rows.append(row_data)
                                    
                        except xlrd.biffh.XLRDError as e:
                            raise Exception(f'Ошибка чтения Excel файла (старый формат .xls): {str(e)}. Убедитесь, что файл не поврежден.')
                        except Exception as e:
                            raise Exception(f'Ошибка при обработке Excel файла: {str(e)}')
                    else:
                        # Новый формат .xlsx - используем openpyxl
                        try:
                            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
                            ws = wb.active
                            
                            # Ищем строку с заголовками (может быть не в первой строке)
                            # Ищем строку, которая содержит ключевые слова заголовков
                            header_row_index = 1
                            headers = []
                            
                            # Проверяем первые 15 строк на наличие заголовков (увеличено для надежности)
                            for row_num in range(1, min(16, ws.max_row + 1)):
                                row = list(ws.iter_rows(min_row=row_num, max_row=row_num))[0]
                                row_values = []
                                for cell in row:
                                    if cell.value is not None:
                                        # Объединяем многострочные заголовки в одну строку
                                        cell_value = str(cell.value).strip()
                                        row_values.append(cell_value)
                                    else:
                                        row_values.append('')
                                
                                # Объединяем все значения строки для проверки
                                row_text = ' '.join(row_values).lower()
                                
                                # Проверяем, есть ли в этой строке ключевые слова заголовков
                                header_keywords = ['артикул', 'номенклатура', 'наименование', 'цена', 'остаток', 'склад', 'розничная', 'фарпост']
                                keyword_count = sum(1 for keyword in header_keywords if keyword in row_text)
                                
                                # Если найдено минимум 2 ключевых слова, считаем это строкой заголовков
                                if keyword_count >= 2:
                                    header_row_index = row_num
                                    # Сохраняем оригинальные заголовки (не в нижнем регистре, чтобы сохранить формат)
                                    headers = row_values
                                    break
                            
                            # Если заголовки не найдены, берем первую строку
                            if not headers:
                                row = list(ws.iter_rows(min_row=1, max_row=1))[0]
                                headers = [str(cell.value or '').strip() for cell in row]
                            
                            # Читаем данные начиная со строки после заголовков
                            for row_num, row in enumerate(ws.iter_rows(min_row=header_row_index + 1, values_only=False), start=header_row_index + 1):
                                row_data = {}
                                for i, cell in enumerate(row):
                                    if i < len(headers) and headers[i]:
                                        header_key = headers[i].lower().strip()
                                        value = cell.value
                                        
                                        # Обрабатываем значение в зависимости от типа
                                        if value is None:
                                            value = ''
                                        elif isinstance(value, (int, float)):
                                            # Для чисел сохраняем как строку, чтобы сохранить форматирование
                                            # Но также сохраняем числовое значение для правильной обработки
                                            if isinstance(value, float) and value.is_integer():
                                                value_str = str(int(value))
                                            else:
                                                value_str = str(value)
                                            # Заменяем точку на запятую для соответствия формату клиента
                                            value_str = value_str.replace('.', ',')
                                            row_data[header_key] = value_str
                                            # Также сохраняем оригинальное значение для числовых полей
                                            if 'цена' in header_key or 'price' in header_key:
                                                row_data[header_key + '_num'] = value
                                            elif 'остаток' in header_key or 'quantity' in header_key or 'склад' in header_key:
                                                row_data[header_key + '_num'] = int(value) if isinstance(value, float) and value.is_integer() else int(value)
                                            continue
                                        else:
                                            value = str(value).strip()
                                        
                                        row_data[header_key] = value
                                
                                # Пропускаем полностью пустые строки
                                has_data = any(
                                    str(v).strip() for v in row_data.values() 
                                    if v is not None and str(v).strip() and not str(v).endswith('_num')
                                )
                                if has_data:
                                    data_rows.append(row_data)
                            
                            wb.close()
                        except openpyxl.utils.exceptions.InvalidFileException as e:
                            raise Exception(f'Файл не является корректным Excel файлом (.xlsx). Возможно, файл поврежден или имеет неправильный формат. Ошибка: {str(e)}')
                        except Exception as e:
                            raise Exception(f'Ошибка при чтении Excel файла: {str(e)}')
                
                # Маппинг колонок для формата прайс-листа клиента
                # Формат: Артикул | Номенклатура, Характеристика. Наименование для печати | Розничная Фарпост RUB Не включает Цена | Склад Уссурийск Остаток
                def normalize_key(key):
                    key_lower = key.lower().strip()
                    
                    # Название товара - из колонки "Номенклатура, Характеристика. Наименование для печати"
                    if 'номенклатура' in key_lower or 'наименование' in key_lower or 'характеристика' in key_lower or 'печать' in key_lower:
                        return 'name'
                    
                    # Артикул
                    if 'артикул' in key_lower or key_lower == 'article':
                        return 'article'
                    
                    # Цена - из колонки "Розничная Фарпост RUB Не включает Цена"
                    if 'цена' in key_lower or 'розничная' in key_lower or 'farpost' in key_lower or 'руб' in key_lower or key_lower == 'price':
                        return 'price'
                    
                    # Остаток - из колонки "Склад Уссурийск Остаток"
                    if 'остаток' in key_lower or 'склад' in key_lower or 'уссурийск' in key_lower or key_lower == 'quantity':
                        return 'quantity'
                    
                    # Стандартные поля (на случай других форматов)
                    if key_lower in ['name', 'brand', 'category', 'description', 'applicability', 'cross_numbers', 'condition', 'availability']:
                        return key_lower
                    
                    return key_lower
                
                # Применяем маппинг колонок
                mapped_rows = []
                for row in data_rows:
                    mapped = {}
                    
                    # Сначала обрабатываем обычные ключи (не _num)
                    for key, value in row.items():
                        # Пропускаем служебные ключи с _num - их обработаем отдельно
                        if key.endswith('_num'):
                            continue
                        
                        mapped_key = normalize_key(key)
                        
                        # Если несколько колонок маппятся на один ключ, берем первую непустую
                        if mapped_key in mapped and mapped[mapped_key]:
                            continue
                        
                        mapped[mapped_key] = value
                    
                    # Теперь обрабатываем числовые значения (_num)
                    for orig_key in row.keys():
                        if orig_key.endswith('_num'):
                            num_value = row[orig_key]
                            base_key = orig_key.replace('_num', '')
                            base_mapped_key = normalize_key(base_key)
                            
                            if base_mapped_key == 'price' or 'цена' in base_key.lower() or 'price' in base_key.lower():
                                mapped['price_num'] = num_value
                            elif base_mapped_key == 'quantity' or 'остаток' in base_key.lower() or 'quantity' in base_key.lower() or 'склад' in base_key.lower():
                                mapped['quantity_num'] = num_value
                                mapped['остаток_num'] = num_value  # Дублируем для надежности
                    
                    mapped_rows.append(mapped)
                
                # Импортируем
                stats = process_bulk_import(
                    mapped_rows, 
                    auto_category=auto_category,
                    auto_brand=auto_brand
                )
                
                messages.success(
                    request,
                    f'✅ Импорт завершён! Создано: {stats["created"]}, обновлено: {stats["updated"]}'
                )
                
                if stats['errors']:
                    messages.warning(
                        request,
                        f'⚠️ Ошибок: {stats["errors"]}'
                    )
                    for error in stats['error_details'][:5]:
                        messages.error(request, error)
                
                return redirect('admin:catalog_product_changelist')
                
            except Exception as e:
                messages.error(request, f'Ошибка при чтении файла: {str(e)}')
    else:
        form = BulkProductImportForm()
    
    return render(request, 'admin/catalog/bulk_product_import.html', {
        'form': form,
        'title': 'Массовый импорт товаров',
    })


@staff_member_required
def quick_add_product(request):
    """Быстрое добавление товара с автоматическим заполнением."""
    if request.method == 'POST':
        form = QuickProductForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data['name']
            price = form.cleaned_data.get('price') or 0
            image = form.cleaned_data.get('image')
            
            # Парсим название
            parsed = parse_product_name(name)
            
            # Создаём категорию если нужно
            category = None
            if parsed['category']:
                category = get_or_create_category(parsed['category'])
            
            # Создаём товар
            product = Product.objects.create(
                name=name,
                article=parsed['article'] or '',
                brand=parsed['brand'] or '',
                category=category,
                price=price,
                is_active=True,
            )
            
            # Загружаем изображение
            if image:
                ProductImage.objects.create(
                    product=product,
                    image=image,
                    is_main=True,
                )
            
            # Сообщения
            success_msg = f'✅ Товар "{product.name}" создан!'
            info_messages = []
            if parsed['brand']:
                info_messages.append(f'🏭 Бренд определён: {parsed["brand"]}')
            if parsed['article']:
                info_messages.append(f'📦 Артикул определён: {parsed["article"]}')
            if parsed['category']:
                info_messages.append(f'📁 Категория: {parsed["category"]}')
            
            # Очищаем форму и показываем сообщения
            form = QuickProductForm()
            messages.success(request, success_msg)
            for msg in info_messages:
                messages.info(request, msg)
            
            # Рендерим страницу без редиректа, чтобы избежать дублирования
            return render(request, 'admin/catalog/quick_add_product.html', {
                'form': form,
                'title': 'Быстрое добавление товара',
            })
    else:
        form = QuickProductForm()
    
    return render(request, 'admin/catalog/quick_add_product.html', {
        'form': form,
        'title': 'Быстрое добавление товара',
    })


@staff_member_required
def download_import_template(request):
    """Скачать шаблон для импорта."""
    response = HttpResponse(
        content_type='text/csv; charset=utf-8-sig'
    )
    response['Content-Disposition'] = 'attachment; filename="import_template.csv"'
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Название', 'Артикул', 'Бренд', 'Цена', 'Категория',
        'Описание', 'Применимость', 'Кросс-номера', 'Наличие', 'Состояние', 'Farpost URL'
    ])
    # Пример данных
    writer.writerow([
        'Стартер Isuzu 10PD1 24V', 'ME220745', 'Isuzu', '15000',
        'Стартеры', 'Новый оригинальный стартер', 'Isuzu Forward, Isuzu Giga',
        '1-81100-141-0, 0-23000-1670', 'in_stock', 'new', ''
    ])
    
    return response

