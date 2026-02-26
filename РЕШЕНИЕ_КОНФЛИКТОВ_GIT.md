# Решение конфликтов Git после pull

## Важные файлы с конфликтами

### 1. catalog/services.py (КРИТИЧНО)
Этот файл был изменен для синхронизации оптового и розничного каталогов. **Нужно принять наши изменения (ваши локальные изменения)**.

**Решение:**
```bash
git checkout --ours catalog/services.py
git add catalog/services.py
```

### 2. catalog/admin_views.py
Также был изменен для обработки оптовых цен. **Принять наши изменения:**
```bash
git checkout --ours catalog/admin_views.py
git add catalog/admin_views.py
```

### 3. catalog/views.py
Был изменен для фильтрации товаров с остатком. **Принять наши изменения:**
```bash
git checkout --ours catalog/views.py
git add catalog/views.py
```

### 4. catalog/models.py
Был изменен для подсчета товаров. **Принять наши изменения:**
```bash
git checkout --ours catalog/models.py
git add catalog/models.py
```

## Остальные файлы

Для остальных файлов (документация, миграции и т.д.) можно принять изменения из удаленной ветки:

```bash
# Принять изменения из удаленной ветки для остальных файлов
git checkout --theirs FARPOST_EXPORT_GUIDE.md
git checkout --theirs admin.py
git checkout --theirs catalog/commerceml_views.py
git checkout --theirs catalog/farpost_views.py
git checkout --theirs catalog/management/commands/process_1c_files.py
git checkout --theirs catalog/management/commands/update_farpost_price_list.py
git checkout --theirs catalog/migrations/0012_synclog_productcharacteristic.py
git checkout --theirs catalog/migrations/0013_add_farpost_auto_update_fields.py
git checkout --theirs catalog/one_c_views.py
git checkout --theirs catalog/sitemaps.py
git checkout --theirs farpost.txt
git checkout --theirs farpost_price.txt
git checkout --theirs logs.md
git checkout --theirs templates/admin/catalog/product_delete_confirmation.html

# Для всех .md файлов документации
git checkout --theirs *.md

# Добавить все разрешенные файлы
git add .
```

## После разрешения конфликтов

```bash
# Зафиксировать слияние
git commit -m "Разрешение конфликтов: приняты изменения синхронизации оптового и розничного каталогов"

# Отправить изменения
git push
```

## Что было изменено в наших файлах

1. **catalog/services.py**: Добавлена синхронизация товаров между retail и wholesale каталогами с правильными ценами
2. **catalog/admin_views.py**: Добавлена обработка оптовых цен при импорте из Excel
3. **catalog/views.py**: Возвращен фильтр `quantity__gt=0` для отображения только товаров с остатком
4. **catalog/models.py**: Возвращен фильтр `quantity__gt=0` в подсчете товаров

## Если нужно вручную разрешить конфликт

Если автоматическое разрешение не подходит, можно вручную:

1. Открыть файл с конфликтом
2. Найти маркеры конфликта:
   - `<<<<<<< HEAD` - ваши локальные изменения
   - `=======` - разделитель
   - `>>>>>>> branch_name` - изменения из удаленной ветки
3. Выбрать нужные части кода
4. Удалить маркеры конфликта
5. Сохранить файл
6. Выполнить `git add <файл>`
