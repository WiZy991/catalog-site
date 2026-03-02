# СРОЧНОЕ исправление дубликата в category.html

## Проблема
На сервере в файле `templates/catalog/category.html` после строки 312 (после `{% endblock %}`) есть дубликат начала файла с еще одним блоком `title` на строке 317.

## Быстрое исправление

### Вариант 1: Автоматический скрипт

```bash
cd ~/onesimus/onesimus

# Создать резервную копию
cp templates/catalog/category.html templates/catalog/category.html.backup

# Удалить все строки после 312-й
head -n 312 templates/catalog/category.html > templates/catalog/category.html.tmp
mv templates/catalog/category.html.tmp templates/catalog/category.html

# Проверить результат
grep -n "block title" templates/catalog/category.html
```

Должен быть только один блок `title` на строке 4.

### Вариант 2: Вручную через nano

```bash
cd ~/onesimus/onesimus
nano templates/catalog/category.html
```

1. Найдите строку 312 с `{% endblock %}`
2. Удалите ВСЕ строки после 312-й (314-327 и далее)
3. Файл должен заканчиваться на строке 312:
   ```django
   });
   </script>
   {% endblock %}
   ```
4. Сохраните (Ctrl+O, Enter, Ctrl+X)

### Вариант 3: Заменить файл целиком

Скопируйте правильный файл `templates/catalog/category.html` с локального компьютера на сервер.

## Проверка после исправления

```bash
# Проверить синтаксис
python3 -m py_compile templates/catalog/category.html

# Проверить количество блоков title (должен быть только 1)
grep -c "block title" templates/catalog/category.html

# Перезапустить
touch tmp/restart.txt

# Проверить логи
tail -f logs/django.log
```

## Правильная структура файла

Файл должен:
- Начинаться с `{% extends 'base.html' %}` на строке 1
- Иметь блок `title` только на строке 4
- Заканчиваться на `{% endblock %}` после `</script>`

НЕ должно быть:
- Дубликата `{% extends 'base.html' %}` на строке 314
- Второго блока `title` на строке 317
- Маркеров конфликта (`=======`, `<<<<<<<`, `>>>>>>>`)
