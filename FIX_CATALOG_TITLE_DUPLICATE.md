# Исправление дубликата блока title в catalog.html

## Проблема
На сервере в файле `templates/catalog/catalog.html` блок `title` появляется более одного раза (на строке 63).

## Решение

### 1. Проверьте файл на сервере

```bash
cd ~/onesimus/onesimus
grep -n "block title" templates/catalog/catalog.html
```

Должен быть только один блок `title` на строке 4.

### 2. Если есть дубликат, удалите его

Откройте файл:
```bash
nano templates/catalog/catalog.html
```

Найдите и удалите все дубликаты блока `title` (кроме первого на строке 4).

Правильная структура должна быть:
```django
{% extends 'base.html' %}
{% load static %}

{% block title %}<title>Каталог товаров - {{ SITE_NAME }}</title>{% endblock %}
{% block meta_description %}Каталог товаров {{ SITE_NAME }}. Автозапчасти с доставкой.{% endblock %}
{% block meta_keywords %}каталог автозапчастей, автозапчасти каталог, купить автозапчасти{% endblock %}

{% block canonical_url %}{{ SEO_BASE_URL }}{% url 'catalog:index' %}{% endblock %}

{% block og_title %}Каталог товаров - {{ SITE_NAME }}{% endblock %}
{% block og_description %}Каталог товаров {{ SITE_NAME }}. Автозапчасти с доставкой.{% endblock %}

{% block breadcrumbs %}
...
{% endblock %}

{% block content %}
...
{% endblock %}
```

### 3. Или замените весь файл

Скопируйте содержимое правильного файла `catalog.html` с локального компьютера на сервер.

### 4. Перезапустите приложение

```bash
touch tmp/restart.txt
```

### 5. Проверьте логи

```bash
tail -f logs/django.log
```

## Важно

Блок `title` должен быть определен только один раз в каждом шаблоне и должен включать тег `<title>`:

```django
{% block title %}<title>Ваш заголовок - {{ SITE_NAME }}</title>{% endblock %}
```

Это соответствует определению блока в `base.html`:
```django
{% block title %}<title>{{ SITE_NAME }}</title>{% endblock %}
```
