git pull --no-rebase
py manage.py makemigrations core
python manage.py migrate
python manage.py makemigrations --merge
python manage.py migrate
   python manage.py collectstatic --noinput
git add .
git commit -m "pull"
python manage.py migrate
py manage.py makemigrations core
git pull --no-rebase
python manage.py migrate
python manage.py makemigrations --merge
git add .
git commit -m "pull"
git pull --no-rebase
python manage.py migrate
python manage.py makemigrations --merge
git add .
git commit -m "pull"
git pull --no-rebase
git add .
git commit -m "pull"
git pull --no-rebase
# 1. Удалите проблемную merge-миграцию
rm catalog/migrations/0006_merge_20260115_1248.py
# 2. Исправьте зависимости в 0006_promotion.py
# Найдите строку с ('catalog', '0004_farpostapisettings_and_more'),
# И замените на ('catalog', '0005_alter_farpostapisettings_packet_id'),
sed -i "s/'catalog', '0004_farpostapisettings_and_more'/'catalog', '0005_alter_farpostapisettings_packet_id'/" catalog/migrations/0006_promotion.py
# 3. Загрузите новую merge-миграцию из репозитория (git pull)
# 4. Примените миграции
rm catalog/migrations/0006_merge_20260115_1248.py
python manage.py migrate
ls -la catalog/migrations/000*.py
python manage.py showmigrations catalog
sed -i "s/'catalog', '0004_farpostapisettings_and_more'/'catalog', '0005_alter_farpostapisettings_packet_id'/" catalog/migrations/0006_promotion.py
grep -A 3 "dependencies" catalog/migrations/0006_promotion.py
git pull
python manage.py migrate
python manage.py migrate catalog 0006_promotion --fake
python manage.py migrate
git add .
git commit -m "pull"
git pull --no-rebase
python manage.py collectstatic --noinput
python manage.py migrate
py manage.py makemigrations core
python manage.py migrate
git add .
git commit -m "pull"
git pull --no-rebase
python manage.py collectstatic --noinput
git pull
py manage.py makemigrations core
python manage.py migrate
python manage.py makemigrations core
python manage.py collectstatic
# Для Passenger обычно достаточно:
touch tmp/restart.txt
touch tmp/restart.txt
git add .
git commit -m "pull"
git pull --no-rebase
git pull
sed -i "s/STATIC_VERSION = '.*'/STATIC_VERSION = '1.2'/" config/settings.py
grep -c "border-radius: 50%" static/css/style.css
grep -c "aspect-ratio" static/css/style.css
git status
git diff static/css/style.css
ls -la media/promotions/
git add .
git commit -m "pull"
git pull --no-rebase
touch tmp/restart.txt
cd ../
touch tmp/restart.txt
find . -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" | grep -i promotion
ls -la media/promotions/ 2>/dev/null || echo "Директория media/promotions/ не существует"
cd onesimus
git add .
git commit -m "pull"
git pull --no-rebase
# 1. Вернитесь в директорию проекта
cd ~/onesimus/onesimus
# 2. Создайте директорию для медиа-файлов
mkdir -p media/promotions
chmod 755 media/promotions
# 3. Проверьте, где находятся изображения акций в БД
python manage.py shell
mkdir -p media/promotions
chmod 755 media/promotions
python manage.py shell
from catalog.models import Promotion
for p in Promotion.objects.all():
    if p.image:;         print(f"ID: {p.id}, Image name:
touch ../tmp/restart.txt
git commit -m "pull"
git add .
git commit -m "pull"
git pull --no-rebase
git add .
git commit -m "pull"
git pull --no-rebase
python manage.py migrate
python manage.py collectstatic
git pull
sed -i "s/STATIC_VERSION = '.*'/STATIC_VERSION = '1.3'/" config/settings.py
find . -name "restart.txt" -o -type d -name "tmp"
git add .
git commit -m "pull"
git pull --no-rebase
python manage.py shell
git pull
grep -A 3 "promotions-carousel__slide" static/css/style.css | head -15
touch ../tmp/restart.txt
python manage.py makemigrations core
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py collectstatic
python manage.py collectstatic --noinput
touch ../tmp/restart.txt
rm -rf static/*
mkdir static
python manage.py collectstatic --noinput
grep -A 3 "promotions-carousel__slide" staticfiles/css/style.css
find . -name style.css
find . -name style.css
mkdir -p static/css
cp staticfiles/css/style.css static/css/style.css
python manage.py collectstatic --noinput
grep -A 3 "promotions-carousel__slide" staticfiles/css/style.css
grep -n "promotions" static/css/style.css
grep -n "promotions" static/css/style.css
grep -R "promotions-carousel__slide" .
git pull
python manage.py collectstatic --noinput
grep -R "promotions-carousel__slide" staticfiles
git add .
git commit -m "pull"
git pull --no-rebase
   cat templates/base.html | grep "style.css"
   ls -la staticfiles/css/style.css
python manage.py collectstatic --noinput
touch tmp/restart.txt
touch ...tmp/restart.txt
git pull origin main
source venv/bin/activate
python manage.py collectstatic --noinput
touch tmp/restart.txt
git config pull.rebase false
git pull origin main
python manage.py collectstatic --noinput
mkdir -p tmp
touch tmp/restart.txt
cat templates/base.html | grep "style.css"
git pull origin main
rm -rf staticfiles/css/*
rm -rf staticfiles/js/*
python manage.py collectstatic --noinput --clear
mkdir -p tmp
touch tmp/restart.txt
ls -lh staticfiles/css/style.css
head -30 staticfiles/css/style.css
ls -lh static/css/style.css
python manage.py shell -c "from django.conf import settings; print('STATIC_ROOT:', settings.STATIC_ROOT)"
ls -la staticfiles/
python manage.py collectstatic --noinput
(venv) onesim8n@lair:~/onesimus/onesimus [0] $ python manage.py collectstatic --noinput
SystemCheckError: System check identified some issues:
ERRORS:
?: (staticfiles.E002) The STATICFILES_DIRS setting should not contain the STATIC_ROOT setting.
(venv) onesim8n@lair:~/onesimus/onesimus [127] $ ?: (staticfiles.E002) The STATICFILES_DIRS setting should not contain the STATIC_ROOT setting.
-bash: syntax error near unexpected token `staticfiles.E002'
(venv) onesim8n@lair:~/onesimus/onesimus [2]
(venv) onesim8n@lair:~/onesimus/onesimus [127] $ ?: (staticfiles.E002) The STATICFILES_DIRS setting should not contain the STATIC_ROOT setting.
-bash: syntax error near unexpected token `staticfiles.E002'
python manage.py collectstatic --noinput
ls -lh staticfiles/css/style.css
ls -lh staticfiles/js/main.js
grep -A 1 "STATIC" config/settings.py |
grep -A 1 "STATIC" config/settings.py 
sed -i "s|STATIC_URL = '/staticfiles/'|STATIC_URL = '/static/'|" config/settings.py
sed -i "s|STATICFILES_DIRS = \[BASE_DIR / 'staticfiles'\]|STATICFILES_DIRS = [BASE_DIR / 'static']|" config/settings.py
sed -i "s|STATIC_ROOT = BASE_DIR / 'static'|STATIC_ROOT = BASE_DIR / 'staticfiles'|" config/settings.py
grep -A 1 "STATIC" config/settings.py
mkdir -p staticfiles
python manage.py collectstatic --noinput
python manage.py collectstatic --noinput
python manage.py collectstatic --noinput
ls -lh staticfiles/css/style.css
ls -lh staticfiles/js/main.js
ls -la staticfiles/
ls -lh staticfiles/css/
ls -lh staticfiles/js/
ls -lh static/css/style.css
ls -lh static/js/main.js
git ls-files static/css/style.css static/js/main.js
ls -la static/
ls -la static/css/ 2>/dev/null || echo "Директория не существует"
git checkout HEAD -- static/css/style.css static/js/main.js
git checkout HEAD -- static/
ls -lh static/css/style.css
ls -lh static/js/main.js
python manage.py collectstatic --noinput
ls -lh staticfiles/css/style.css
ls -lh staticfiles/js/main.js
touch tmp/restart.txt
git pull origin main
grep -n "aspect-ratio.*1 / 1" static/css/style.css
grep -n "border-radius: 50%" static/css/style.css | grep "category" | head -3
python manage.py collectstatic --noinput
touch tmp/restart.txt
grep -n "header__cart" static/css/style.css | head -10
grep -n "category-card__icon" static/css/style.css | head -5
grep -n "promotions-carousel" static/css/style.css | head -3
wc -l static/css/style.css
wc -l static/js/main.js
ls -lh static/css/cart.css
grep -A 10 "\.header__cart {" static/css/style.css | grep -E "(aspect-ratio|width.*44|height.*44)"
grep -A 5 "\.category-card__icon {" static/css/style.css | grep "border-radius"
grep -A 5 "\.catalog-category__icon {" static/css/style.css | grep "border-radius"
grep -c "promotions-carousel" static/css/style.css
grep -c "initPromotionsCarousel" static/js/main.js
git fetch origin
git reset --hard origin/main
wc -l static/css/style.css static/js/main.js
grep -n "aspect-ratio.*1 / 1" static/css/style.css
grep -n "border-radius: 50%" static/css/style.css | grep "category" | head -3
grep -c "promotions-carousel" static/css/style.css
grep -c "initPromotionsCarousel" static/js/main.js
python manage.py collectstatic --noinput
touch tmp/restart.txt
python manage.py collectstatic
python manage.py collectstatic --noinput
git pull origin main
git add .
git commit -m "pull"
git pull origin main
git pull --no-rebase
git add .
git commit -m "pull"
git pull --no-rebase
git pull --no-rebase
python manage.py collectstatic --noinput
sed -n '110,120p' config/settings.py
python manage.py collectstatic --noinput
python manage.py collectstatic --noinput
touch tmp/restart.txt
git add .
git commit -m "action"
git pull --no rebase
git pull --no-rebase
python manage.py collectstatic --noinput
touch tmp/restart.txt
git checkout HEAD -- config/settings.py
git pull origin main

touch tmp/restart.txt
git pull origin main
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git pull origin main
git add .
git commit -m "action"
git pull origin main
git pull --no-rebase
git add .
git commit -m "action"
git pull --no-rebase
git pull origin main
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git pull --no-rebase
git add .
git commit -m "action"
git pull origin main
git pull --no-rebase
git add .
python manage.py collectstatic --noinput
grep -n "promotionsCarouselInitialized"
git checkout HEAD -- static/js/main.js
python manage.py collectstatic --noinput --clear
ls -lh staticfiles/js/main.js
touch tmp/restart.txt
git pull origin main
grep -n "AUTOPLAY_DELAY = 5000" static/js/main.js
python manage.py collectstatic --noinput --clear
ls -lh staticfiles/js/main.js
ls -lh staticfiles/css/style.css
grep -n "AUTOPLAY_DELAY = 5000" staticfiles/js/main.js
touch tmp/restart.txt
grep "STATIC_VERSION" config/settings.py
git pull origin main
touch tmp/restart.txt
grep "STATIC_VERSION" config/settings.py
git pull origin main
git add .
git pull origin main
git commit -m "fix"
git pull origin main
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git pull --no-rebase
git pull origin main
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git add .
git commit -m "fix"
git pull origin main
git pull --no-rebase
git add .
git commit -m "fix"
git pull --no-rebase
git pull --no-rebase
git pull origin main
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git add .
git pull --no-rebase
git pull --no-rebase
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git pull --no-rebase
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git stash
git checkout -- static/css/style.css
git pull --no-rebase
git checkout --theirs static/css/style.css
git add static/css/style.css
git commit -m "Разрешение конфликта: использование версии из репозитория"
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git merge --abort
git fetch origin main
git reset --hard origin/main
python manage.py collectstatic --noinput --clear
touch tmp/restart.txt
git merge --abort
git fetch origin main
git reset --hard origin/main
grep -n "AUTOPLAY_DELAY = 5000" static/js/main.js
grep "object-fit: contain" static/css/style.css
python manage.py collectstatic --noinput --clear
grep -n "AUTOPLAY_DELAY = 5000" staticfiles/js/main.js
grep "object-fit: contain" staticfiles/css/style.css | head -1
touch tmp/restart.txt
cd omesimus
cd onesimus
source venv/bin/activate
cd onesimus
git add .
git pull --no-rebase
python manage.py collectstatic --noinput --clear
cd onesimus
source venv/bin/activate
cd onesimus
git add .
git pull --no-rebase
git commit -m "fix"
git pull --no-rebase
git fetch origin main
git pull origin main
git add .
git commit -m "fix"

git pull origin main
git pull --no-rebase
git add .
git commit -m "fix"
git pull --no-rebase
git pull origin main
touch tmp/restart.txt
python manage.py collectstatic --noinput --clear
git pull --no-rebase
git add .
git commit -m "fix"
git pull --no-rebase
touch tmp/restart.txt
git pull origin main
git add .
git commit -m "fix"
git pull --no-rebase
git pull origin main
touch tmp/restart.txt
git push origin man
git push origin main
git add .
git commit -m "fix"
git pull --no-rebase
git status
git add .
git pull --no-rebase
cd onesin
cd onesim
cd onesimus
source venv/bin/activate
cd onesimus
git add .
git pull --no-rebase
git commit -m "fix"
git fetch origin main
git reset --hard origin/main
git merge --abort
git add .
git pull --no-rebase
git commit -m "fix"
git pull origin main
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
mkdir -p tmp
touch tmp/restart.txt
git pull origin main
ls -la core/urls.py core/views.py templates/core/consent.html
echo "=== core/urls.py ==="
cat core/urls.py
echo ""
echo "=== ConsentView в core/views.py ==="
grep -A 5 "class ConsentView" core/views.py
echo ""
echo "=== Подключение core.urls в config/urls.py ==="
grep "core.urls" config/urls.py
echo ""
echo "=== Очистка кэша и перезапуск ==="
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
mkdir -p tmp
touch tmp/restart.txt
echo "✓ Приложение перезапущено"
ls -la core/urls.py core/views.py templates/core/consent.html
python manage.py show_urls | grep consent
python manage.py check
python manage.py shell
tail -50 ~/logs/error.log 2>/dev/null || tail -50 ~/logs/passenger.log 2>/dev/null
ls -la tmp/restart.txt
stat tmp/restart.txt
git add .
git pull --no-rebase
git commit -m "fix"
git pull --no-rebase
git pull origin main
cd onesimus
source venv/bin/activate
cd onesimus
git pull --no-rebase
git pull --no-rebase
git add .
git commit -m "fix"
git pull --no-rebase
git pull origin main
grep "Promotion" catalog/admin.py
cd onesimus
source venv/bin/activate
cd onesimus
git pull
cd onesimus
cd onesimus
cd onesimus
cd ../
source venv/bin/activate
cd onesimus
git add .
git pull --no-rebase
cd onesimus
source venv/bin/activate
cd onesimus
git add .
git pull --no-rebase
git add .
git commit -m "Завершение слияния"
git pull --no-rebase
git add .
git commit -m "Завершение слияния"
git pull --no-rebase
git status
git fetch origin
git log HEAD..origin/main
git pull --no-rebase
git add .
git commit -m "Завершение слияния"
git pull origin main
python manage.py collectstatic --noinput
cd onesimus
source venv/bin/activate
cd onesimus
git add .
git pull --no-rebase
git commit -m "Завершение слияния"
git pull --no-rebase
git fetch origin
git log HEAD..origin/main
git pull --no-rebase
git add .
git pull --no-rebase
git add .
git commit -m "Завершение слияния"
git pull --no-rebase
python manage.py collectstatic --noinput
grep -n "block title" templates/catalog/product.html
