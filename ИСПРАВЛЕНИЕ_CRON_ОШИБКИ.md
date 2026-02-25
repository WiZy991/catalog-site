# Исправление ошибки cron: Directory nonexistent

## ❌ Проблема

В логе видна ошибка:
```
cannot create /onesimus/onesimus/logs/cron_1c_import.log: Directory nonexistent
```

**Причины:**
1. Неправильный путь в команде cron (относительный вместо абсолютного)
2. Возможно, директория `logs/` не существует в нужном месте

## ✅ Решение

### Шаг 1: Убедитесь, что директория logs/ существует

Через SSH выполните:

```bash
cd ~/onesimus/onesimus
mkdir -p logs
chmod 755 logs
ls -la logs
```

Должны увидеть файлы `commerceml_requests` и `django`.

### Шаг 2: Узнайте правильные пути

Выполните через SSH:

```bash
# Текущая директория проекта
pwd

# Путь к Python
which python

# Путь к директории logs
ls -la logs
```

**Пример вывода:**
- Базовый путь: `/home/o/onesim8n/onesimus/onesimus`
- Python: `/home/o/onesim8n/onesimus/venv/bin/python`
- Logs: `/home/o/onesim8n/onesimus/onesimus/logs`

### Шаг 3: Исправьте команду в cron

В планировщике Beget используйте **ПОЛНЫЙ АБСОЛЮТНЫЙ ПУТЬ**:

```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files --recent 10 >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
```

**Важно:** 
- Замените `/home/o/onesim8n/onesimus/onesimus` на ваш реальный путь (из `pwd`)
- Замените `/home/o/onesim8n/onesimus/venv/bin/python` на ваш реальный путь к Python (из `which python`)

### Шаг 4: Проверьте команду вручную

Перед настройкой cron проверьте команду:

```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files --recent 10 >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
```

После выполнения проверьте:
```bash
cat logs/cron_1c_import.log
```

Если файл создался и содержит вывод - команда правильная!

### Шаг 5: Обновите задание в Beget

1. Откройте планировщик заданий в Beget
2. Найдите ваше задание
3. Отредактируйте его
4. Вставьте **ПРАВИЛЬНУЮ** команду с полными путями
5. Сохраните

## 🔍 Альтернативный вариант: без лог-файла

Если проблемы с путями продолжаются, можно временно убрать запись в лог-файл:

```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files --recent 10
```

Но лучше исправить пути и использовать лог-файл для отладки.

## 📋 Правильный формат команды

**Структура:**
```bash
cd <АБСОЛЮТНЫЙ_ПУТЬ_К_ПРОЕКТУ> && <АБСОЛЮТНЫЙ_ПУТЬ_К_PYTHON> manage.py process_1c_files --recent 10 >> <АБСОЛЮТНЫЙ_ПУТЬ_К_ЛОГУ> 2>&1
```

**Пример (замените на ваши пути!):**
```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files --recent 10 >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
```

## ⚠️ Частые ошибки

1. **Относительные пути** - не работают в cron
   - ❌ `cd onesimus/onesimus`
   - ✅ `cd /home/o/onesim8n/onesimus/onesimus`

2. **Неправильный путь к Python**
   - ❌ `python manage.py`
   - ✅ `/home/o/onesim8n/onesimus/venv/bin/python manage.py`

3. **Неправильный путь к лог-файлу**
   - ❌ `>> logs/cron_1c_import.log`
   - ✅ `>> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log`

## ✅ Проверка после исправления

1. Подождите 5-10 минут после сохранения задания
2. Проверьте файл `logs/cron_1c_import.log` через файловый менеджер Beget
3. Или через SSH:
   ```bash
   cat logs/cron_1c_import.log
   ```

Если файл создался и содержит вывод - всё работает правильно! 🎉
