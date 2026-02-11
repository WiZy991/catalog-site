# Команды для перезапуска Django на beget

## Способ 1: Через touch файла (самый простой)

```bash
cd ~/onesimus/onesimus
touch tmp/restart.txt
```

Если папки `tmp` нет, создайте её:
```bash
mkdir -p tmp
touch tmp/restart.txt
```

## Способ 2: Через Passenger (если установлен)

```bash
cd ~/onesimus/onesimus
passenger-config restart-app $(pwd)
```

Или:
```bash
cd ~/onesimus/onesimus
~/.passenger/standalone/versions/*/bin/passenger-config restart-app $(pwd)
```

## Способ 3: Через always_restart.txt

```bash
cd ~/onesimus/onesimus
mkdir -p tmp
touch tmp/always_restart.txt
```

## Способ 4: Найти и перезапустить процесс

```bash
# Найти процесс Passenger/Django
ps aux | grep -E "passenger|python.*manage.py|gunicorn" | grep -v grep

# Если нашли процесс, отправить HUP сигнал
kill -HUP <PID>

# Или найти все процессы и перезапустить
pkill -HUP -f passenger
```

## Способ 5: Через beget API (если доступен)

```bash
# Проверьте, есть ли команда beget
which beget
beget restart
```

## Рекомендуемый способ для beget:

```bash
cd ~/onesimus/onesimus
mkdir -p tmp
touch tmp/restart.txt
sleep 2
curl -I "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth"
```

После выполнения `touch tmp/restart.txt` Passenger автоматически перезапустит приложение при следующем запросе.
