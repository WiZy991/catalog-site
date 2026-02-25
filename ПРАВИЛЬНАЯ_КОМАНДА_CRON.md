# Правильная команда для cron (на основе вашей структуры)

## 📁 Структура вашего сервера

Из скриншотов видно:
- Корневая директория: `/home/o/onesim8n/`
- Проект находится в: `/home/o/onesim8n/onesimus/onesimus/`
- Папка `logs/` существует: `/home/o/onesim8n/onesimus/onesimus/logs/`
- Файл `cron_1c_import.log` уже создан! ✅

## ✅ Правильная команда для cron

### Вариант 1: С записью в лог-файл (рекомендуется) - обрабатывает все новые файлы

```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
```

**Примечание:** Без флага `--recent` скрипт обрабатывает все файлы без маркера `.processed`, независимо от времени изменения. Это лучше для автоматической обработки новых файлов от 1С.

### Вариант 2: Только файлы за последние 10 минут (если нужно ограничение по времени)

```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files --recent 10 >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
```

**Примечание:** Используйте `--recent 10` только если хотите обрабатывать только свежие файлы. Для автоматической обработки всех новых файлов от 1С лучше использовать вариант 1 (без `--recent`).

## 🔧 Настройка в Beget

### Через "Мастер заданий":

1. **Команда для выполнения:**
   ```bash
   cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
   ```
   
   **Примечание:** Без флага `--recent` обрабатываются все новые файлы (без маркера `.processed`).

2. **Описание задания:**
   ```
   Автоматический импорт товаров от 1С
   ```

3. **Расписание:**
   - **В указанные минуты:** `*/5` (каждые 5 минут)
   - **В указанные часы:** оставьте пустым или `*`
   - Нажмите: "В любой день недели", "Каждый день", "Каждый месяц"

4. Нажмите **"Добавить задание"**

### Через "Составить задание вручную":

1. **Cron выражение:**
   ```
   */5 * * * *
   ```

2. **Команда:**
   ```bash
   cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
   ```

3. Сохраните задание

## 🧪 Проверка команды

Перед настройкой cron проверьте команду через SSH:

```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files --recent 10 >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
```

После выполнения проверьте лог-файл:

```bash
cat logs/cron_1c_import.log
```

Или через файловый менеджер Beget откройте файл `logs/cron_1c_import.log`.

## 📊 Варианты расписания

### Каждые 5 минут (рекомендуется):
- Cron: `*/5 * * * *`
- Параметр: без `--recent` (обрабатывает все новые файлы)

### Каждые 15 минут:
- Cron: `*/15 * * * *`
- Параметр: `--recent 20`

### Каждый час:
- Cron: `0 * * * *`
- Параметр: `--recent 65`

### Раз в день (в 3:00):
- Cron: `0 3 * * *`
- Параметр: без `--recent` или `--recent 1440` (24 часа)

## ✅ Проверка работы

После настройки cron:

1. Подождите 5-10 минут
2. Проверьте файл `logs/cron_1c_import.log` через файловый менеджер Beget
3. Файл должен обновляться с новыми записями

Если файл обновляется - всё работает правильно! 🎉

## 🔍 Если что-то не работает

1. **Проверьте путь к Python:**
   ```bash
   which python
   ```
   Должен быть: `/home/o/onesim8n/onesimus/venv/bin/python`

2. **Проверьте путь к проекту:**
   ```bash
   pwd
   ```
   Должен быть: `/home/o/onesim8n/onesimus/onesimus`

3. **Проверьте права на директорию logs:**
   ```bash
   ls -la logs/
   ```
   Должны быть права `755` или `700`

4. **Проверьте логи cron в Beget:**
   - Откройте планировщик заданий
   - Найдите ваше задание
   - Посмотрите "Лог работы скрипта"

## 📝 Итоговая команда (скопируйте в Beget)

```bash
cd /home/o/onesim8n/onesimus/onesimus && /home/o/onesim8n/onesimus/venv/bin/python manage.py process_1c_files >> /home/o/onesim8n/onesimus/onesimus/logs/cron_1c_import.log 2>&1
```

**Cron выражение:** `*/5 * * * *` (каждые 5 минут)

**Важно:** Эта команда обрабатывает все новые файлы (без маркера `.processed`). Если нужно обрабатывать только файлы за последние 10 минут, добавьте `--recent 10` перед `>>`.
