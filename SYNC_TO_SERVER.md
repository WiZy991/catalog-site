# Синхронизация изменений с сервером

## Быстрая инструкция

### 1. На локальной машине (Windows):

```powershell
# Перейдите в директорию проекта
cd c:\Users\Антон\Desktop\web

# Проверьте статус изменений
git status

# Добавьте все изменения
git add .

# Закоммитьте изменения
git commit -m "Обновление: исправление CSS"

# Отправьте изменения на сервер
git push origin main
```

### 2. На сервере (SSH):

```bash
# Перейдите в директорию проекта
cd ~/onesimus/onesimus

# Загрузите изменения из репозитория
git pull origin main

# Активируйте виртуальное окружение (если нужно)
source venv/bin/activate

# Соберите статические файлы (ВАЖНО для CSS/JS!)
python manage.py collectstatic --noinput

# Перезапустите приложение
touch tmp/restart.txt

# Или если используется другой способ перезапуска:
# systemctl restart your-service-name
```

## Важные моменты:

1. **Всегда выполняйте `collectstatic`** после изменений в CSS/JS файлах
2. **Перезапускайте приложение** после изменений в Python коде или настройках
3. **Очистите кеш браузера** на клиенте (Ctrl+Shift+R) или откройте в режиме инкогнито

## Если изменения не применяются:

1. Проверьте, что файлы действительно обновились на сервере:
   ```bash
   ls -la templates/base.html
   cat templates/base.html | grep "style.css"
   ```

2. Проверьте, что статические файлы собраны:
   ```bash
   ls -la staticfiles/css/style.css
   ```

3. Проверьте права доступа:
   ```bash
   chmod -R 755 staticfiles/
   chmod -R 755 media/
   ```

4. Проверьте конфигурацию веб-сервера (nginx/apache) - он должен обслуживать `/static/` и `/media/`

## Автоматический скрипт для сервера

Создайте файл `update.sh` на сервере:

```bash
#!/bin/bash
cd ~/onesimus/onesimus
git pull origin main
source venv/bin/activate
python manage.py collectstatic --noinput
touch tmp/restart.txt
echo "Обновление завершено!"
```

Затем просто запускайте:
```bash
bash update.sh
```
