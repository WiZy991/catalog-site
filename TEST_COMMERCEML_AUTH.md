# Тестирование CommerceML авторизации

## ✅ URL работает!

Получен ответ 401 вместо 404 - это означает, что URL найден и обрабатывается.

## Тестирование авторизации

### Тест 1: Проверка авторизации через curl

```bash
# Замените USERNAME и PASSWORD на логин и пароль администратора Django
curl -v -u "USERNAME:PASSWORD" "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth"
```

**Ожидаемый ответ при успешной авторизации:**
```
success
1c_exchange_session
<значение_cookie>
```

### Тест 2: Проверка через Python

```bash
python manage.py shell
```

```python
import requests
from django.contrib.auth import get_user_model

# Получите пользователя администратора
User = get_user_model()
admin = User.objects.filter(is_staff=True).first()
print(f"Администратор: {admin.username}")

# Тест запроса (замените на реальные данные)
import base64
username = "ваш_логин"
password = "ваш_пароль"
auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()

headers = {
    'Authorization': f'Basic {auth_string}'
}

response = requests.get(
    "http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth",
    headers=headers
)
print(f"Статус: {response.status_code}")
print(f"Ответ: {response.text}")
```

## Настройка в 1С

Теперь можно настроить обмен в 1С:

1. **Адрес сайта:** `http://onesim8n.beget.tech/cml/exchange/?type=catalog&mode=checkauth`
2. **Имя пользователя:** Логин администратора Django
3. **Пароль:** Пароль администратора Django

## Следующие шаги

После настройки в 1С выполните "Проверку соединения" - должно появиться сообщение "Соединение успешно установлено".

Затем можно выполнить полный обмен данными.
