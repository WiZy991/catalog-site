# Отладка проблемы с URL

## Шаг 1: Проверьте, что файл обновлен

```bash
cd ~/onesimus/onesimus
cat config/urls.py | grep -A 2 "cml/exchange"
```

Должны увидеть строки с `path('cml/exchange/')`.

## Шаг 2: Проверьте импорт через manage.py shell

```bash
python manage.py shell
```

В shell выполните:

```python
# Проверка импорта commerceml_views
try:
    from catalog import commerceml_views
    print("✓ commerceml_views импортирован")
    print(f"Функция: {commerceml_views.commerceml_exchange}")
except Exception as e:
    print(f"✗ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()

# Проверка импорта urls.py
try:
    from config import urls
    print(f"✓ config.urls импортирован")
    print(f"Количество паттернов: {len(urls.urlpatterns)}")
    
    # Поиск cml в urlpatterns
    found = False
    for i, p in enumerate(urls.urlpatterns):
        if hasattr(p, 'pattern'):
            pattern_str = str(p.pattern)
            if 'cml' in pattern_str:
                print(f"✓ Найден паттерн #{i}: {pattern_str}")
                print(f"  View: {p.callback}")
                found = True
    
    if not found:
        print("✗ Паттерн cml/exchange не найден в urlpatterns")
        print("\nПервые 10 паттернов:")
        for i, p in enumerate(urls.urlpatterns[:10]):
            print(f"  {i+1}. {p.pattern if hasattr(p, 'pattern') else p}")
except Exception as e:
    print(f"✗ Ошибка импорта urls: {e}")
    import traceback
    traceback.print_exc()
```

## Шаг 3: Если паттерн не найден, проверьте строки в файле

```bash
# Проверьте, что строки точно есть
grep -n "cml" config/urls.py

# Проверьте строку с импортом
grep -n "commerceml_views" config/urls.py
```

## Шаг 4: Если импорт работает, но паттерн не загружается

Возможно, есть ошибка при создании паттерна. Проверьте синтаксис:

```bash
python manage.py check
```

## Шаг 5: Альтернативное решение - добавить URL напрямую

Если ничего не помогает, можно временно добавить URL в другом месте, например в `core/urls.py` или создать отдельный файл.
