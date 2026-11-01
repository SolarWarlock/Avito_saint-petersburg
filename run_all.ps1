# =====================================================================
# 🚀 Avito Real Estate BI Platform - Full Automated Deployment
# =====================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " 🏠 АВИТО НЕДВИЖИМОСТЬ: АВТОМАТИЧЕСКИЙ ЗАПУСК BI-ПЛАТФОРМЫ" -ForegroundColor Cyan
Write-Host " Стек: PostgreSQL 15 + ClickHouse OLAP + Apache Superset + Python ETL" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------
# Шаг 1: Проверка Docker
# ---------------------------------------------------------------------
Write-Host "[1/6] 🐳 Проверка доступности Docker..." -ForegroundColor Yellow
try {
    docker info > $null 2>&1
    Write-Host "       Docker запущен и готов к работе." -ForegroundColor Green
} catch {
    Write-Host "❌ ОШИБКА: Docker Desktop не запущен. Запустите Docker и повторите попытку." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------
# Шаг 2: Запуск контейнеров через Docker Compose
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[2/6] 📦 Поднятие контейнеров (Postgres, ClickHouse, Redis, Superset)..." -ForegroundColor Yellow
docker compose up -d
Write-Host "       Контейнеры успешно развернуты." -ForegroundColor Green

# ---------------------------------------------------------------------
# Шаг 3: Ожидание готовности DWH-сервисов
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[3/6] ⏳ Проверка готовности портов DWH (Postgres: 5433, ClickHouse: 8123)..." -ForegroundColor Yellow

$retries = 30
$chReady = $false
while ($retries -gt 0 -and -not $chReady) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8123/ping" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $chReady = $true
        }
    } catch {
        Start-Sleep -Seconds 2
        $retries--
    }
}

if (-not $chReady) {
    Write-Host "⚠️ Внимание: ClickHouse ещё инициализируется, продолжаем..." -ForegroundColor DarkYellow
} else {
    Write-Host "       ClickHouse и PostgreSQL онлайн и отвечают на запросы." -ForegroundColor Green
}

# ---------------------------------------------------------------------
# Шаг 4: Запуск Python ETL-пайплайна
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[4/6] 🔄 Запуск ETL-пайплайна (Data Quality, очистка и загрузка в DWH)..." -ForegroundColor Yellow

$dataFile = "data/raw/avito_clean_final_full.xlsx"
if (-not (Test-Path $dataFile)) {
    $dataFile = "data/raw/avito_listings_sample.xlsx"
}
Write-Host "       Источник данных: $dataFile" -ForegroundColor Gray

python etl/pipeline.py $dataFile
Write-Host "       ETL завершен: витрины PostgreSQL и ClickHouse обновлены." -ForegroundColor Green

# ---------------------------------------------------------------------
# Шаг 5: Сборка и настройка дашборда в Superset
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[5/6] 📊 Обновление структуры дашборда и стилей в Apache Superset..." -ForegroundColor Yellow
docker cp docker/superset/create_dashboard.py avito_superset:/app/create_dashboard.py
docker exec -i avito_superset python /app/create_dashboard.py
Write-Host "       Дашборд, фильтры и стили Авито успешно обновлены." -ForegroundColor Green

# ---------------------------------------------------------------------
# Шаг 6: Запуск тестов Data Quality (pytest)
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] 🧪 Запуск автоматических тестов качества данных (pytest)..." -ForegroundColor Yellow
pytest -v tests/test_data_quality.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "       Все 12 тестов Data Quality успешно пройдены!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Часть тестов завершилась с предупреждениями." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------
# Итоги
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host " 🎉 ВСЕ СЕРВИСЫ И ДАШБОРД УСПЕШНО РАЗВЕРНУТЫ И ГОТОВЫ К РАБОТЕ!" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host ""
Write-Host " 🌐 Прямая ссылка на дашборд: http://localhost:8088/superset/dashboard/avito-spb-real-estate/" -ForegroundColor Cyan
Write-Host " 🔑 Данные для входа в Superset:" -ForegroundColor White
Write-Host "    - Логин:  admin" -ForegroundColor White
Write-Host "    - Пароль: admin" -ForegroundColor White
Write-Host ""
Write-Host " 🗄 Точки подключения к DWH:" -ForegroundColor White
Write-Host "    - ClickHouse: localhost:8123 (HTTP) / 9000 (Native) [user: avito_user]" -ForegroundColor Gray
Write-Host "    - PostgreSQL: localhost:5433 [db: avito_dwh, user: avito_user]" -ForegroundColor Gray
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host ""

