# Отключение перехвата nginx для статики

## Проблема
На старом домене `onesim8n.beget.tech` всё работало без nginx. На новом домене `onesimus25.ru` nginx перехватывает запросы к `/static/` и возвращает 404.

## Решение 1: Создать конфигурацию nginx, которая передает запросы в Django

Если nginx перехватывает запросы, можно настроить его так, чтобы он передавал запросы в Django (Passenger), а не возвращал 404:

```bash
cd ~/onesimus/onesimus
mkdir -p .nginx

cat > .nginx/onesimus25.ru.conf << 'EOF'
# НЕ обслуживаем статику напрямую, передаем в Django
location /static/ {
    # Передаем запрос в Passenger/Django
    try_files $uri @passenger;
}

location @passenger {
    # Передаем в Django через Passenger
    passenger_enabled on;
}
EOF

cp .nginx/onesimus25.ru.conf .nginx/www.onesimus25.ru.conf
touch tmp/restart.txt
```

## Решение 2: Проверить, есть ли дефолтная конфигурация nginx

Возможно, Beget автоматически создал конфигурацию для нового домена, которая блокирует `/static/`:

```bash
# Проверьте, есть ли конфигурация в других местах
find ~ -name "*onesimus25.ru*" -type f 2>/dev/null
find ~ -name "*.conf" -path "*nginx*" 2>/dev/null

# Проверьте, что в .nginx
ls -la .nginx/
cat .nginx/*.conf 2>/dev/null
```

## Решение 3: Убедиться, что Django view вызывается

Проверьте, что паттерн для статики действительно первый в `urlpatterns`:

```bash
# Проверьте порядок URL паттернов
grep -A 10 "urlpatterns = \[" config/urls.py | head -20
grep -B 5 -A 5 "static" config/urls.py
```

## Решение 4: Временно включить DEBUG=True для теста

Если при `DEBUG=True` статика работает, значит проблема в кастомном view при `DEBUG=False`:

```bash
# Временно включите DEBUG
sed -i "s/DEBUG = False/DEBUG = True/" config/settings.py

# Перезапустите
touch tmp/restart.txt

# Проверьте
curl -I https://onesimus25.ru/static/css/style.css

# Если работает - проблема в кастомном view
# Если не работает - проблема в nginx/Passenger
```

## Решение 5: Проверить конфигурацию Passenger

Возможно, на новом домене изменилась конфигурация Passenger. Проверьте файл `.htaccess` или `passenger_wsgi.py`:

```bash
# Проверьте .htaccess
cat .htaccess 2>/dev/null

# Проверьте конфигурацию Passenger
ls -la public/
cat public/.htaccess 2>/dev/null
```

## Решение 6: Сравнить со старым доменом

Если старый домен еще работает, сравните конфигурации:

```bash
# На старом домене (если доступен)
# Проверьте, есть ли там конфигурация nginx
ls -la .nginx/

# Проверьте настройки в панели Beget
# Возможно, там была другая конфигурация для старого домена
```

## Самое простое решение

Если раньше работало без nginx, попробуйте создать пустую конфигурацию nginx, которая ничего не делает:

```bash
cd ~/onesimus/onesimus
mkdir -p .nginx

# Создайте пустую конфигурацию (nginx будет использовать дефолтную)
touch .nginx/onesimus25.ru.conf
touch .nginx/www.onesimus25.ru.conf

touch tmp/restart.txt
```

Или создайте конфигурацию, которая явно передает запросы в Django:

```bash
cat > .nginx/onesimus25.ru.conf << 'EOF'
# Явно передаем все запросы в Passenger/Django
location / {
    passenger_enabled on;
}
EOF
```
