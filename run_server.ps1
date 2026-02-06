# Скрипт для запуска Django сервера
# Использование: .\run_server.ps1

# Используем Python напрямую из виртуального окружения
$pythonPath = Join-Path $PSScriptRoot "venv\Scripts\python.exe"

if (Test-Path $pythonPath) {
    Write-Host "Запуск сервера Django..." -ForegroundColor Green
    & $pythonPath manage.py runserver
} else {
    Write-Host "Ошибка: Python не найден в venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "Попробуйте активировать виртуальное окружение вручную:" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "  python manage.py runserver" -ForegroundColor Yellow
}
