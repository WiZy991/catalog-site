# Исправление ошибки IndentationError на сервере

## Проблема
```
IndentationError: unindent does not match any outer indentation level (services.py, line 371)
```

Это происходит из-за смешанных табов и пробелов в файле.

## Решение

### Вариант 1: Через SSH (рекомендуется)

```bash
cd ~/onesimus/onesimus

# Замените все табы на пробелы в файле
python3 -c "
with open('catalog/services.py', 'rb') as f:
    content = f.read()
content = content.replace(b'\t', b'    ')
with open('catalog/services.py', 'wb') as f:
    f.write(content)
print('Готово!')
"

# Проверьте синтаксис
python -m py_compile catalog/services.py

# Если ошибок нет, перезапустите приложение
touch tmp/restart.txt
```

### Вариант 2: Через FileZilla

1. Скачайте файл `catalog/services.py` с сервера
2. Откройте его в редакторе (например, VS Code)
3. Убедитесь, что все отступы используют **только пробелы** (4 пробела на уровень)
4. Особенно проверьте строки 359-375
5. Загрузите исправленный файл обратно на сервер
6. Перезапустите приложение

### Вариант 3: Использовать скрипт fix_services_indent.py

Загрузите файл `fix_services_indent.py` на сервер и выполните:

```bash
cd ~/onesimus/onesimus
python3 fix_services_indent.py
python -m py_compile catalog/services.py
touch tmp/restart.txt
```

## Проверка правильности отступов

Строки 359-375 должны иметь следующие отступы:
- Строка 359: `if result['brand']:` - 4 пробела
- Строки 360-361: внутри if - 8 пробелов
- Строка 364: `if brand_upper in [...]` - 8 пробелов
- Строки 365-368: внутри вложенного if - 12 пробелов
- Строка 370: комментарий - 8 пробелов
- Строка 371: `if not result['article']:` - 8 пробелов
- Строки 372-374: внутри if - 12 пробелов
- Строка 375: пустая строка - 4 пробела (закрывает блок `if result['brand']:`)

## После исправления

После исправления отступов сайт должен заработать. Проверьте:

```bash
# Проверьте синтаксис
python -m py_compile catalog/services.py

# Если ошибок нет, перезапустите
touch tmp/restart.txt

# Проверьте логи на наличие других ошибок
tail -f /path/to/logs/error.log
```
