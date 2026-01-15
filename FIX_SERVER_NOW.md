# СРОЧНО: Исправление на сервере

## Выполните эти команды на сервере ПРЯМО СЕЙЧАС:

```bash
cd ~/onesimus/onesimus

# 1. Настройте git для merge (решает проблему с divergent branches)
git config pull.rebase false

# 2. Загрузите изменения
git pull origin main

# 3. Соберите статические файлы
python manage.py collectstatic --noinput

# 4. Создайте директорию tmp и перезапустите приложение
mkdir -p tmp
touch tmp/restart.txt

# 5. Проверьте, что изменения применились
cat templates/base.html | grep "style.css"
```

## Ожидаемый результат:

В выводе `cat templates/base.html | grep "style.css"` должно быть:
```
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    <link rel="stylesheet" href="{% static 'css/cart.css' %}">
```

**БЕЗ** параметра `?v=...` в конце!

## Если git pull всё ещё не работает:

```bash
# Сначала посмотрите статус
git status

# Если есть локальные изменения, которые конфликтуют:
git stash
git pull origin main
git stash pop

# Или принудительно обновите (ОСТОРОЖНО - потеряете локальные изменения на сервере!)
git fetch origin
git reset --hard origin/main
```

## После выполнения команд:

1. Очистите кеш браузера (Ctrl+Shift+R)
2. Или откройте сайт в режиме инкогнито
3. Проверьте, что CSS загружается
