# Скрипт для проверки и отправки изменений

Write-Host "=== Проверка статуса ===" -ForegroundColor Green
git status

Write-Host ""
Write-Host "=== Проверка последних коммитов ===" -ForegroundColor Yellow
git log --oneline -5

Write-Host ""
Write-Host "=== Проверка, отправлены ли изменения ===" -ForegroundColor Yellow
$localCommit = git rev-parse HEAD
$remoteCommit = git rev-parse origin/main 2>$null

if ($LASTEXITCODE -eq 0) {
    if ($localCommit -eq $remoteCommit) {
        Write-Host "Локальные и удаленные коммиты совпадают" -ForegroundColor Green
    } else {
        Write-Host "Есть неотправленные коммиты!" -ForegroundColor Red
        Write-Host "Локальный: $localCommit" -ForegroundColor White
        Write-Host "Удаленный: $remoteCommit" -ForegroundColor White
        Write-Host ""
        Write-Host "Отправляю изменения..." -ForegroundColor Yellow
        git push origin main
    }
} else {
    Write-Host "Не удалось получить информацию об удаленном репозитории" -ForegroundColor Yellow
    Write-Host "Попытка отправки..." -ForegroundColor Yellow
    git push origin main
}

Write-Host ""
Write-Host "=== Готово! ===" -ForegroundColor Green
