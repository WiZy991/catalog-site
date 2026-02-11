# Исправление проблемы с CommerceML URL

## Проблема
URL `cml/exchange/` не виден в списке URL паттернов, хотя файл обновлен.

## Решение

### Шаг 1: Проверьте, что файл действительно обновлен на сервере

```bash
cd ~/onesimus/onesimus
cat config/urls.py | head -50 | tail -10
```

Должны увидеть строки с `cml/exchange/`.

### Шаг 2: Проверьте синтаксис файла

```bash
python -m py_compile config/urls.py
```

Если есть ошибки - исправьте их.

### Шаг 3: Проверьте импорт модуля

```bash
python manage.py shell
>>> from catalog import commerceml_views
>>> print(commerceml_views.commerceml_exchange)
```

Если ошибка - исправьте файл `catalog/commerceml_views.py`.

### Шаг 4: Проверьте, что импорт в urls.py работает

```bash
python manage.py shell
>>> from config.urls import urlpatterns
>>> [str(p.pattern) for p in urlpatterns if 'cml' in str(p.pattern)]
```

### Шаг 5: Принудительная перезагрузка через beget

1. Зайдите в панель beget
2. Остановите приложение полностью
3. Подождите 10-15 секунд
4. Запустите приложение заново

### Шаг 6: Альтернатива - проверьте, может быть файл не синхронизирован

Если вы редактировали файл локально, убедитесь, что он загружен на сервер:

```bash
# Проверьте дату изменения файла
ls -la config/urls.py
ls -la catalog/commerceml_views.py
```

### Шаг 7: Если ничего не помогает - добавьте URL вручную через другой способ

Можно временно добавить URL в основной urls.py напрямую, без импорта:

```python
# В config/urls.py вместо:
from catalog import commerceml_views
path('cml/exchange/', commerceml_views.commerceml_exchange, ...)

# Попробуйте:
from catalog.commerceml_views import commerceml_exchange
path('cml/exchange/', commerceml_exchange, name='commerceml_exchange'),
```
