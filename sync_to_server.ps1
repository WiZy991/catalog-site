# Скрипт для синхронизации изменений с сервером
# Запустите этот скрипт после внесения изменений

Write-Host "=== Синхронизация изменений с сервером ===" -ForegroundColor Green
Write-Host ""

# Проверка статуса git
Write-Host "1. Проверка статуса git..." -ForegroundColor Yellow
git status

Write-Host ""
Write-Host "2. Добавление всех изменений..." -ForegroundColor Yellow
git add .

Write-Host ""
Write-Host "3. Создание коммита..." -ForegroundColor Yellow
$commitMessage = Read-Host "Введите сообщение коммита (или нажмите Enter для стандартного)"
if ([string]::IsNullOrWhiteSpace($commitMessage)) {
    $commitMessage = "Обновление: исправление CSS и синхронизация с сервером"
}
git commit -m $commitMessage

Write-Host ""
Write-Host "4. Отправка изменений на сервер..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "=== Готово! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Теперь на сервере выполните:" -ForegroundColor Cyan
Write-Host "  cd ~/onesimus/onesimus" -ForegroundColor White
Write-Host "  git pull origin main" -ForegroundColor White
Write-Host "  source venv/bin/activate" -ForegroundColor White
Write-Host "  python manage.py collectstatic --noinput" -ForegroundColor White
Write-Host "  touch tmp/restart.txt" -ForegroundColor White
Write-Host ""
