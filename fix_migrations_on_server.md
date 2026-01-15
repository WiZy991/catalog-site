# Инструкция по исправлению миграций на сервере

## Проблема
На сервере есть проблемная merge-миграция `0006_merge_20260115_1248.py`, которая ссылается на несуществующую миграцию `0005_promotion_alter_farpostapisettings_packet_id`.

## Решение

Выполните на сервере следующие команды:

```bash
# 1. Перейдите в директорию проекта
cd /home/o/onesim8n/onesimus/onesimus

# 2. Активируйте виртуальное окружение
source venv/bin/activate

# 3. Удалите проблемную merge-миграцию
rm catalog/migrations/0006_merge_20260115_1248.py

# 4. Измените зависимости в 0006_promotion.py
# Отредактируйте файл catalog/migrations/0006_promotion.py
# Найдите строку:
#     dependencies = [
#         ('catalog', '0004_farpostapisettings_and_more'),
#     ]
# И замените на:
#     dependencies = [
#         ('catalog', '0005_alter_farpostapisettings_packet_id'),
#     ]

# 5. После этого загрузите новую merge-миграцию 0007_merge_0005_and_0006.py (из репозитория)

# 6. Примените миграции
python manage.py migrate
```

## Альтернативный вариант (через редактирование файлов)

```bash
# 1. Удалите проблемную merge-миграцию
rm catalog/migrations/0006_merge_20260115_1248.py

# 2. Исправьте зависимости в 0006_promotion.py
sed -i "s/'catalog', '0004_farpostapisettings_and_more'/'catalog', '0005_alter_farpostapisettings_packet_id'/" catalog/migrations/0006_promotion.py

# 3. Загрузите 0007_merge_0005_and_0006.py из репозитория (git pull)

# 4. Примените миграции
python manage.py migrate
```
