# Исправление ошибок вложенных блоков в шаблонах

## Проблема
В `templates/base.html` были вложенные блоки с одинаковыми именами, что вызывало ошибку:
```
TemplateSyntaxError: 'block' tag with name 'title' appears more than once
TemplateSyntaxError: 'block' tag with name 'meta_description' appears more than once
```

## Что исправлено

### 1. Блок `title`
**Было (неправильно):**
```django
<meta name="title" content="{% block meta_title %}{% block title %}{{ SITE_NAME }}{% endblock %}{% endblock %}">
```

**Стало (правильно):**
```django
<meta name="title" content="{% block meta_title %}{{ SITE_NAME }}{% endblock %}">
```

### 2. Блок `og_title`
**Было (неправильно):**
```django
<meta property="og:title" content="{% block og_title %}{% block title %}{{ SITE_NAME }}{% endblock %}{% endblock %}">
```

**Стало (правильно):**
```django
<meta property="og:title" content="{% block og_title %}{{ SITE_NAME }}{% endblock %}">
```

### 3. Блок `twitter_title`
**Было (неправильно):**
```django
<meta name="twitter:title" content="{% block twitter_title %}{% block title %}{{ SITE_NAME }}{% endblock %}{% endblock %}">
```

**Стало (правильно):**
```django
<meta name="twitter:title" content="{% block twitter_title %}{{ SITE_NAME }}{% endblock %}">
```

### 4. Блок `og_description`
**Было (неправильно):**
```django
<meta property="og:description" content="{% block og_description %}{% block meta_description %}{{ SITE_DESCRIPTION }}{% endblock %}{% endblock %}">
```

**Стало (правильно):**
```django
<meta property="og:description" content="{% block og_description %}{{ SITE_DESCRIPTION }}{% endblock %}">
```

### 5. Блок `twitter_description`
**Было (неправильно):**
```django
<meta name="twitter:description" content="{% block twitter_description %}{% block meta_description %}{{ SITE_DESCRIPTION }}{% endblock %}{% endblock %}">
```

**Стало (правильно):**
```django
<meta name="twitter:description" content="{% block twitter_description %}{{ SITE_DESCRIPTION }}{% endblock %}">
```

## Как это работает теперь

1. Каждый блок независим и имеет значение по умолчанию
2. Дочерние шаблоны могут переопределять любой блок отдельно
3. Нет конфликтов имен блоков

## Пример использования в дочерних шаблонах

```django
{% extends 'base.html' %}

{% block title %}Мой заголовок - {{ SITE_NAME }}{% endblock %}
{% block meta_description %}Мое описание{% endblock %}
{% block og_title %}Мой OG заголовок{% endblock %}
{% block og_description %}Мое OG описание{% endblock %}
```

## После исправления

1. Загрузите обновленный `templates/base.html` на сервер
2. Перезапустите приложение:
   ```bash
   touch tmp/restart.txt
   ```
3. Проверьте сайт - все страницы должны работать
