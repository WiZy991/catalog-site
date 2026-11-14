#!/usr/bin/env bash
# Безопасное обновление кода на сервере БЕЗ затирания БД и media.
# Запуск на сервере из корня сайта:
#   bash deploy_safe.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

stamp="$(date +%Y%m%d_%H%M%S)"
mkdir -p backups

echo "==> Backup db.sqlite3 (если есть)"
if [ -f db.sqlite3 ]; then
  cp -a db.sqlite3 "backups/db.sqlite3.${stamp}"
  echo "    backups/db.sqlite3.${stamp}"
fi

echo "==> Backup media (если есть)"
if [ -d media ]; then
  tar -czf "backups/media.${stamp}.tar.gz" media || true
  echo "    backups/media.${stamp}.tar.gz"
fi

echo "==> git fetch/pull (код только)"
git fetch origin
# Не даём git удалить/перезаписать локальную БД при pull, если она ещё tracked
git update-index --skip-worktree db.sqlite3 2>/dev/null || true
git update-index --assume-unchanged db.sqlite3 2>/dev/null || true

git pull --ff-only origin main || git pull --ff-only origin master

# Если pull всё же убрал файл БД — восстанавливаем из бэкапа
if [ ! -f db.sqlite3 ] && [ -f "backups/db.sqlite3.${stamp}" ]; then
  echo "==> Восстанавливаю db.sqlite3 из бэкапа"
  cp -a "backups/db.sqlite3.${stamp}" db.sqlite3
fi

echo "==> venv + migrate + collectstatic"
if [ -f venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput

mkdir -p tmp
touch tmp/restart.txt
touch .restart-app 2>/dev/null || true

echo "==> Готово. Каталог в БД не трогали."
