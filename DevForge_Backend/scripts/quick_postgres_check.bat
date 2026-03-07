@echo off
REM DevForge Quick PostgreSQL Check for Windows
REM Usage: quick_postgres_check.bat

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   DevForge Quick PostgreSQL Check
echo ========================================
echo.

REM Database connection details
set DB_CONTAINER=devforge-postgres
set DB_USER=devforge
set DB_NAME=devforge

REM Check if PostgreSQL container is running
echo [INFO] Checking PostgreSQL Container Status...
docker ps | findstr /i "%DB_CONTAINER%" >nul
if %errorlevel% neq 0 (
    echo [ERROR] PostgreSQL container is not running
    echo [INFO] Please start PostgreSQL with: docker-compose up -d postgres
    pause
    exit /b 1
)
echo [SUCCESS] PostgreSQL container is running

REM Quick stats
echo.
echo Quick Database Stats:
echo ------------------------
echo Database Size:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT pg_size_pretty(pg_database_size('%DB_NAME%')) as size;"

echo.
echo Table Counts:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT relname as tablename, n_live_tup as rows, pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as size FROM pg_stat_user_tables WHERE schemaname = 'public' ORDER BY n_live_tup DESC;"

echo.
echo Users ^& API Keys:
echo --------------------
echo Total Users:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT COUNT(*) FROM users;"

echo Admin Users:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT COUNT(*) FROM users WHERE is_admin = true;"

echo Active Users:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT COUNT(*) FROM users WHERE is_active = true;"

echo Total API Keys:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT COUNT(*) FROM api_keys;"

echo Active API Keys:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT COUNT(*) FROM api_keys WHERE is_active = true;"

echo.
echo Tier Configuration:
echo ----------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT tier, hourly_limit, monthly_limit, cost_per_1k_tokens, is_active FROM tier_config ORDER BY tier;"

echo.
echo Recent Usage (Last 24h):
echo -----------------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT COUNT(*) as total_requests, COUNT(DISTINCT user_id) as unique_users, COUNT(CASE WHEN success = false THEN 1 END) as errors FROM request_logs WHERE created_at >= NOW() - INTERVAL '24 hours';"

echo.
echo API Keys with Overrides:
echo ---------------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT ak.name, ak.tier, ak.hourly_limit_override, ak.monthly_limit_override, u.email as user_email FROM api_keys ak LEFT JOIN users u ON ak.user_id = u.id WHERE ak.hourly_limit_override IS NOT NULL OR ak.monthly_limit_override IS NOT NULL ORDER BY ak.created_at DESC;"

echo.
echo [SUCCESS] Quick check completed!
pause
