# Просмотр логов обмена с 1С

## Где смотреть логи

### 1. Логи Django (файл)

После добавления настроек логирования, логи будут писаться в файл:

```bash
cd ~/onesimus/onesimus
tail -100 logs/django.log | grep -i "commerceml\|1c\|handle_file\|handle_import"
```

Или посмотреть все логи CommerceML:

```bash
grep -i "commerceml\|handle_file\|handle_import" logs/django.log | tail -50
```

### 2. Логи в админ-панели Django

1. Зайдите: `http://onesim8n.beget.tech/admin/catalog/synclog/`
2. Откройте последнюю запись
3. Проверьте все поля

### 3. Проверка через shell

```bash
python manage.py shell
```

```python
from catalog.models import SyncLog
from django.utils import timezone
from datetime import timedelta

# Последние логи за последний час
recent_time = timezone.now() - timedelta(hours=1)
logs = SyncLog.objects.filter(created_at__gte=recent_time).order_by('-created_at')

print(f"Логов за последний час: {logs.count()}")
for log in logs:
    print(f"\n{log.created_at}: {log.get_status_display()}")
    print(f"  Файл: {log.filename}")
    print(f"  Обработано: {log.processed_count}, Создано: {log.created_count}, Обновлено: {log.updated_count}")
```

## Что делать после обмена в 1С

1. **Сразу проверьте директорию обмена:**
   ```bash
   ls -lah ~/onesimus/onesimus/media/1c_exchange/
   ```

2. **Проверьте логи Django:**
   ```bash
   tail -50 ~/onesimus/onesimus/logs/django.log
   ```

3. **Проверьте логи синхронизации:**
   - В админке: Catalog → Sync logs
   - Или через shell (см. выше)

4. **Если файлы есть, но логов нет:**
   - Файлы загружаются, но не обрабатываются
   - Проверьте, вызывается ли режим `import`
   - Проверьте логи на ошибки

## Диагностика проблемы

### Если логов нет вообще:

1. Проверьте, что запросы доходят до сервера
2. Проверьте логи Django на наличие запросов
3. Убедитесь, что все этапы обмена проходят (checkauth → init → file → import)

### Если файлы есть, но товары не создаются:

1. Проверьте структуру XML файла
2. Проверьте логи синхронизации на ошибки
3. Проверьте, что товары найдены в файле

### Если товары создаются, но не видны на сайте:

1. Проверьте, что `is_active=True`
2. Проверьте, что товары привязаны к категориям
3. Проверьте фильтры на сайте
