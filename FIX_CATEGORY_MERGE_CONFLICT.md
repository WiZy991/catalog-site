# Исправление конфликта слияния в category.html

## Проблема
На сервере в файле `templates/catalog/category.html` остались маркеры конфликта слияния Git:
- Строка 314: `=======`
- Строка 318: дубликат блока `title`

## Решение

### Вариант 1: Удалить маркеры конфликта вручную

```bash
cd ~/onesimus/onesimus
nano templates/catalog/category.html
```

Найдите и удалите все строки с маркерами конфликта:
- `=======`
- `<<<<<<< HEAD` (если есть)
- `>>>>>>> ...` (если есть)

Удалите также дубликат начала файла (строки 315-328), оставьте только правильную версию в начале файла.

### Вариант 2: Автоматическое удаление маркеров

```bash
cd ~/onesimus/onesimus
# Удалить все маркеры конфликта
sed -i '/^=======$/d' templates/catalog/category.html
sed -i '/^<<<<<<</d' templates/catalog/category.html
sed -i '/^>>>>>>>/d' templates/catalog/category.html

# Удалить дубликат начала файла (строки после endblock extra_js)
# Нужно вручную проверить файл после этого
```

### Вариант 3: Заменить файл целиком

Скопируйте правильный файл `templates/catalog/category.html` с локального компьютера на сервер.

## Правильная структура файла

Файл должен начинаться так:
```django
{% extends 'base.html' %}
{% load static %}

{% block title %}<title>{{ category.get_meta_title }} - {{ SITE_NAME }}</title>{% endblock %}
{% block meta_description %}{{ category.get_meta_description }}{% endblock %}
...
```

И заканчиваться так:
```django
    }
});
</script>
{% endblock %}
```

**НЕ должно быть:**
- Маркеров конфликта (`=======`, `<<<<<<<`, `>>>>>>>`)
- Дубликата начала файла
- Двух блоков `title`

## После исправления

1. Проверьте синтаксис:
```bash
python3 -m py_compile templates/catalog/category.html
```

2. Перезапустите приложение:
```bash
touch tmp/restart.txt
```

3. Проверьте логи:
```bash
tail -f logs/django.log
```

4. Проверьте сайт:
```bash
curl -I http://onesim8n.beget.tech/catalog/detali-podveski/
```
