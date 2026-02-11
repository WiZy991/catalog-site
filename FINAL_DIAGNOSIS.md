# Финальная диагностика обмена с 1С

## Проблема
Запросы от 1С после checkauth не доходят до Django - нет логов.

## Что сделано

1. ✅ Добавлено логирование во все функции CommerceML
2. ✅ Добавлен кеш Django для сессий
3. ✅ Временно отключена проверка cookie
4. ✅ Добавлен middleware для логирования ВСЕХ запросов к /cml/exchange/

## Проверка

### 1. Перезапустите сервер:

```bash
cd ~/onesimus/onesimus
touch tmp/restart.txt
sleep 5
```

### 2. Выполните обмен в 1С

### 3. Проверьте логи:

```bash
# Проверить все записи middleware
tail -200 logs/django.log | grep -E "MIDDLEWARE|CommerceML|checkauth|init|file|import"

# Или все последние записи
tail -50 logs/django.log
```

## Что должно быть в логах

Если запросы доходят до Django, должны быть записи:
1. `MIDDLEWARE: CommerceML запрос получен` - для КАЖДОГО запроса
2. `handle_checkauth вызван` - для checkauth
3. `handle_init вызван` - для init
4. `handle_file вызван` - для file
5. `handle_import вызван` - для import

## Если логов все еще нет

Если после добавления middleware логов все еще нет, значит:

1. **Запросы не доходят до Django вообще**
   - Проблема в настройках веб-сервера (nginx)
   - Проблема в настройках Passenger
   - Запросы блокируются на уровне сети

2. **Проблема в настройках 1С**
   - 1С не переходит к следующим этапам после checkauth
   - Неправильный URL в настройках 1С
   - Ошибка в ответе checkauth

## Альтернативная проверка

Попробуйте сделать тестовый запрос вручную:

```bash
# 1. checkauth
curl -v -u "admin:password" "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth" 2>&1 | head -30

# 2. Проверить логи
tail -20 logs/django.log

# 3. Если получили cookie, используйте его для init
curl -v -b "1c_exchange_session=COOKIE_VALUE" "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=init" 2>&1 | head -30

# 4. Проверить логи снова
tail -20 logs/django.log
```

Если в логах появляются записи при ручных запросах, но не появляются при обмене из 1С - проблема в настройках 1С.
