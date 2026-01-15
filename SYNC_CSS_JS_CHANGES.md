# Синхронизация изменений CSS/JS с сервером

## Проблема:
На локальной машине работают:
- ✅ Квадратная корзина (aspect-ratio: 1 / 1)
- ✅ Карусель акций (работает)
- ✅ Круглые картинки категорий (border-radius: 50%)

На сервере:
- ❌ Вытянутая корзина
- ❌ Сломанная карусель акций
- ❌ Квадратные картинки категорий

## Решение:

### 1. На локальной машине (Windows):

```powershell
cd c:\Users\Антон\Desktop\web

# Проверьте статус
git status

# Добавьте изменения в CSS и JS
git add static/css/style.css static/css/cart.css static/js/main.js

# Закоммитьте
git commit -m "Исправление фронтенда: квадратная корзина, карусель акций, круглые категории"

# Отправьте на сервер
git push origin main
```

### 2. На сервере (SSH):

```bash
cd ~/onesimus/onesimus

# Загрузите изменения
git pull origin main

# Соберите статические файлы
python manage.py collectstatic --noinput

# Перезапустите приложение
touch tmp/restart.txt

# Проверьте, что стили применились
grep -n "aspect-ratio.*1 / 1" staticfiles/css/style.css
grep -n "border-radius: 50%" staticfiles/css/style.css | head -5
```

## Что должно быть в CSS:

1. **Корзина (квадратная):**
   - `.header__cart` должен иметь `aspect-ratio: 1 / 1 !important;`
   - Размеры: `width: 44px !important; height: 44px !important;`

2. **Категории (круглые):**
   - `.category-card__icon` должен иметь `border-radius: 50%;`
   - `.category-card__icon img` должен иметь `border-radius: 50%;`
   - `.catalog-category__icon` должен иметь `border-radius: 50%;`
   - `.catalog-category__icon img` должен иметь `border-radius: 50%;`

3. **Карусель акций:**
   - Должны быть стили `.promotions-carousel*`
   - Должен быть JavaScript `initPromotionsCarousel()` в `main.js`

## Проверка на сервере:

```bash
# Проверьте корзину
grep -A 5 "\.header__cart {" staticfiles/css/style.css | grep "aspect-ratio"

# Проверьте категории
grep "border-radius: 50%" staticfiles/css/style.css | grep "category"

# Проверьте карусель
grep "promotions-carousel" staticfiles/css/style.css | head -3
grep "initPromotionsCarousel" staticfiles/js/main.js
```

Если все проверки пройдены, очистите кеш браузера (Ctrl+Shift+R) и проверьте сайт!
