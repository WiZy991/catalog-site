# Скрипт для проверки и синхронизации фронтенд изменений

Write-Host "=== Проверка фронтенд изменений ===" -ForegroundColor Green
Write-Host ""

# Проверка статуса git
Write-Host "1. Проверка статуса git..." -ForegroundColor Yellow
$gitStatus = git status --short
if ($gitStatus) {
    Write-Host "Найдены незакоммиченные изменения:" -ForegroundColor Red
    git status --short
    Write-Host ""
    Write-Host "ВАЖНО: Есть незакоммиченные изменения!" -ForegroundColor Red
    Write-Host "Нужно закоммитить их перед отправкой на сервер." -ForegroundColor Yellow
} else {
    Write-Host "Все изменения закоммичены." -ForegroundColor Green
}

Write-Host ""
Write-Host "2. Проверка последних коммитов..." -ForegroundColor Yellow
git log --oneline -5 --name-only -- "static/css/*" "static/js/*" "templates/*"

Write-Host ""
Write-Host "3. Проверка изменений в CSS/JS файлах..." -ForegroundColor Yellow
$cssFiles = Get-ChildItem -Path "static\css\*.css" -Recurse
$jsFiles = Get-ChildItem -Path "static\js\*.js" -Recurse

Write-Host "CSS файлы:" -ForegroundColor Cyan
foreach ($file in $cssFiles) {
    $lastModified = (Get-Item $file.FullName).LastWriteTime
    Write-Host "  $($file.Name) - изменен: $lastModified" -ForegroundColor White
}

Write-Host ""
Write-Host "JS файлы:" -ForegroundColor Cyan
foreach ($file in $jsFiles) {
    $lastModified = (Get-Item $file.FullName).LastWriteTime
    Write-Host "  $($file.Name) - изменен: $lastModified" -ForegroundColor White
}

Write-Host ""
Write-Host "4. Проверка, что файлы в git..." -ForegroundColor Yellow
$trackedFiles = git ls-files "static/css/*" "static/js/*"
if ($trackedFiles) {
    Write-Host "Файлы отслеживаются git:" -ForegroundColor Green
    $trackedFiles | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
} else {
    Write-Host "ВНИМАНИЕ: CSS/JS файлы не отслеживаются git!" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Инструкция для синхронизации ===" -ForegroundColor Green
Write-Host ""
Write-Host "Если есть незакоммиченные изменения:" -ForegroundColor Yellow
Write-Host "  1. git add static/css/* static/js/* templates/*" -ForegroundColor White
Write-Host "  2. git commit -m 'Обновление фронтенда'" -ForegroundColor White
Write-Host "  3. git push origin main" -ForegroundColor White
Write-Host ""
Write-Host "На сервере выполните:" -ForegroundColor Yellow
Write-Host "  1. git pull origin main" -ForegroundColor White
Write-Host "  2. python manage.py collectstatic --noinput" -ForegroundColor White
Write-Host "  3. touch tmp/restart.txt" -ForegroundColor White
Write-Host ""
