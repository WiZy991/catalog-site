# Правильная проверка URL через manage.py

## Выполните на сервере:

```bash
cd ~/onesimus/onesimus
python manage.py shell
```

Затем в shell выполните:

```python
# Проверка импорта
from catalog import commerceml_views
print("✓ commerceml_views импортирован")

# Проверка функции
print(commerceml_views.commerceml_exchange)
print("✓ Функция существует")

# Проверка URL паттернов
from django.urls import get_resolver
resolver = get_resolver()
patterns = [str(p.pattern) for p in resolver.url_patterns]

# Поиск cml в паттернах
cml_patterns = [p for p in patterns if 'cml' in p]
print(f"Найдено паттернов с 'cml': {cml_patterns}")

# Если не найдено, проверим все паттерны
if not cml_patterns:
    print("\nВсе URL паттерны:")
    for i, p in enumerate(patterns[:30], 1):
        print(f"{i}. {p}")
```

## Если URL не найдены, проверьте импорт в urls.py:

```python
# Проверка импорта в urls.py
from config import urls
print("✓ config.urls импортирован")

# Проверка urlpatterns
print(f"Количество паттернов: {len(urls.urlpatterns)}")

# Поиск cml в urlpatterns
for p in urls.urlpatterns:
    if hasattr(p, 'pattern'):
        pattern_str = str(p.pattern)
        if 'cml' in pattern_str:
            print(f"Найден паттерн: {pattern_str}")
            print(f"  View: {p.callback}")
```

## Если все еще не работает, проверьте файл напрямую:

```bash
# Проверьте, что строки есть в файле
grep -n "cml/exchange" config/urls.py

# Проверьте синтаксис
python manage.py check
```
