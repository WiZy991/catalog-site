# Скрипт для принудительной синхронизации изменений на сервер

Write-Host "=== Проверка статуса Git ===" -ForegroundColor Green
git status

Write-Host ""
Write-Host "=== Добавление всех изменений ===" -ForegroundColor Yellow
git add -A

Write-Host ""
Write-Host "=== Коммит изменений ===" -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "Обновление фронтенда: $timestamp"

Write-Host ""
Write-Host "=== Отправка на сервер ===" -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "=== Проверка отправки ===" -ForegroundColor Green
$localCommit = git rev-parse HEAD
$remoteCommit = git rev-parse origin/main 2>$null

if ($LASTEXITCODE -eq 0) {
    if ($localCommit -eq $remoteCommit) {
        Write-Host "✓ Изменения успешно отправлены!" -ForegroundColor Green
        Write-Host "Локальный коммит: $localCommit" -ForegroundColor White
    } else {
        Write-Host "⚠ Коммиты не совпадают" -ForegroundColor Yellow
        Write-Host "Локальный: $localCommit" -ForegroundColor White
        Write-Host "Удаленный: $remoteCommit" -ForegroundColor White
    }
} else {
    Write-Host "⚠ Не удалось проверить удаленный репозиторий" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Готово! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Теперь на сервере выполните:" -ForegroundColor Cyan
Write-Host "  cd ~/onesimus/onesimus" -ForegroundColor White
Write-Host "  git pull origin main" -ForegroundColor White
Write-Host "  python manage.py collectstatic --noinput --clear" -ForegroundColor White
Write-Host "  touch tmp/restart.txt" -ForegroundColor White
