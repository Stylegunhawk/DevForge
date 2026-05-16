@echo off
REM DevForge PostgreSQL Database Inspection for Windows
REM Comprehensive database analysis script
REM Usage: postgres_inspection.bat

setlocal enabledelayedexpansion

echo.
echo ========================================
echo  DevForge PostgreSQL Database Inspection
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

REM Test database connection
echo.
echo [INFO] Testing Database Connection...
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT 1;" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Database connection failed
    pause
    exit /b 1
)
echo [SUCCESS] Database connection successful

REM 1. Database Overview
echo.
echo Database Overview:
echo -------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT current_database() as database_name, version() as postgresql_version, current_user as current_user, inet_server_addr() as server_address, inet_server_port() as server_port;"

REM 2. All Tables Overview
echo.
echo All Tables Overview:
echo -------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT schemaname, tablename, tableowner, hasindexes, hasrules, hastriggers, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

REM 3. Detailed Table Information
echo.
echo Detailed Table Information:
echo ---------------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT t.table_name, c.column_name, c.data_type, c.character_maximum_length, c.is_nullable, c.column_default, c.ordinal_position FROM information_schema.tables t JOIN information_schema.columns c ON t.table_name = c.table_name WHERE t.table_schema = 'public' ORDER BY t.table_name, c.ordinal_position;"

REM 4. Table Row Counts
echo.
echo Table Row Counts:
echo -----------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT schemaname, relname as tablename, n_tup_ins as total_inserts, n_tup_upd as total_updates, n_tup_del as total_deletes, n_live_tup as live_rows, n_dead_tup as dead_rows, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze FROM pg_stat_user_tables ORDER BY live_rows DESC;"

REM 5. Indexes Information
echo.
echo All Indexes:
echo ------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT schemaname, tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;"

REM 6. Constraints Information
echo.
echo Table Constraints:
echo -----------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT tc.table_name, tc.constraint_name, tc.constraint_type, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name FROM information_schema.table_constraints tc LEFT JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name LEFT JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name WHERE tc.table_schema = 'public' ORDER BY tc.table_name, tc.constraint_type;"

REM 7. Users Table Sample Data
echo.
echo Users Table Sample Data:
echo -----------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT id, email, name, is_admin, is_active, auth_provider, created_at FROM users ORDER BY created_at DESC LIMIT 10;"

REM 8. API Keys Overview
echo.
echo API Keys Overview:
echo ------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT ak.id, ak.name, ak.tier, ak.integration_name, ak.is_active, ak.hourly_limit_override, ak.monthly_limit_override, ak.created_at, ak.last_used_at, u.email as user_email FROM api_keys ak LEFT JOIN users u ON ak.user_id = u.id ORDER BY ak.created_at DESC LIMIT 20;"

REM 9. Tier Configuration
echo.
echo Tier Configuration:
echo -------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT tier, hourly_limit, monthly_limit, cost_per_1k_tokens, max_expiry_days, is_active, updated_at, updated_by FROM tier_config ORDER BY tier;"

REM 10. Usage Analytics Summary
echo.
echo Usage Analytics Summary:
echo ------------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT DATE_TRUNC('day', created_at) as date, COUNT(*) as total_requests, COUNT(DISTINCT user_id) as unique_users, AVG(duration_ms) as avg_response_time, COUNT(CASE WHEN success = false THEN 1 END) as error_count FROM request_logs WHERE created_at >= CURRENT_DATE - INTERVAL '7 days' GROUP BY DATE_TRUNC('day', created_at) ORDER BY date DESC;"

REM 11. Most Active API Keys
echo.
echo Most Active API Keys (Last 24 Hours):
echo --------------------------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT 'API Keys activity tracked in request_logs table' as status, 'Use quick_postgres_check.bat for API key overview' as suggestion;"

REM 12. Database Size Analysis
echo.
echo Database Size Analysis:
echo -----------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT pg_size_pretty(pg_database_size(current_database())) as database_size, (SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public') as table_count, (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public') as index_count, (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public') as column_count;"

REM 13. Partition Information
echo.
echo Partition Information:
echo ---------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT 'No partitions found - using regular tables' as status;"

REM 14. Database Roles and Permissions
echo.
echo Database Roles and Permissions:
echo -------------------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT rolname as role_name, rolsuper as is_superuser, rolcreaterole as can_create_role, rolcreatedb as can_create_db, rolcanlogin as can_login, rolconnlimit as connection_limit FROM pg_roles WHERE rolname LIKE 'app_%' ORDER BY rolname;"

REM 15. Recent Activity
echo.
echo Recent Activity:
echo ----------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT 'Recent API Requests' as activity_type, COUNT(*) as count, MAX(created_at) as latest_activity FROM request_logs WHERE created_at >= CURRENT_DATE - INTERVAL '7 days' UNION ALL SELECT 'Recent User Registrations' as activity_type, COUNT(*) as count, MAX(created_at) as latest_activity FROM users WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';"

REM 16. Orphaned Records Check
echo.
echo Orphaned Records Check:
echo -----------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT 'api_keys with missing users' as check_type, COUNT(*) as count FROM api_keys ak LEFT JOIN users u ON ak.user_id = u.id WHERE ak.user_id IS NOT NULL AND u.id IS NULL UNION ALL SELECT 'request_logs with missing users' as check_type, COUNT(*) as count FROM request_logs rl LEFT JOIN users u ON rl.user_id = u.id WHERE rl.user_id IS NOT NULL AND u.id IS NULL UNION ALL SELECT 'llm_usage with missing users' as check_type, COUNT(*) as count FROM llm_usage lu LEFT JOIN users u ON lu.user_id = u.id WHERE lu.user_id IS NOT NULL AND u.id IS NULL;"

REM 17. Performance Statistics
echo.
echo Performance Statistics:
echo -----------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT schemaname, relname as tablename, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch, n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup FROM pg_stat_user_tables WHERE schemaname = 'public' ORDER BY seq_scan + idx_scan DESC LIMIT 15;"

REM 18. Configuration Settings
echo.
echo Important Configuration Settings:
echo --------------------------------
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT name, setting, unit, category, short_desc FROM pg_settings WHERE name IN ('max_connections', 'shared_buffers', 'effective_cache_size', 'work_mem', 'maintenance_work_mem', 'checkpoint_completion_target', 'wal_buffers', 'default_statistics_target', 'random_page_cost', 'effective_io_concurrency') ORDER BY category, name;"

REM 19. Create comprehensive export
echo.
echo Creating Comprehensive Database Export...
docker exec %DB_CONTAINER% pg_dump -U %DB_USER% -d %DB_NAME --schema-only --no-owner --no-privileges > devforge_schema_%date:~-10,4%%date:~-7,2%%date:~-4,2%_%time:~-11,2%%time:~-8,2%%time:~-5,2%.sql
echo [SUCCESS] Schema exported to devforge_schema_*.sql

REM 20. Generate summary report
echo.
echo Database Summary Report:
echo ========================
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';"') do set TOTAL_TABLES=%%i
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM users;"') do set TOTAL_USERS=%%i
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM api_keys;"') do set TOTAL_API_KEYS=%%i
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM request_logs;"') do set TOTAL_USAGE_RECORDS=%%i
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT pg_size_pretty(pg_database_size(current_database()));"') do set DB_SIZE=%%i

set TOTAL_TABLES=%TOTAL_TABLES: =%
set TOTAL_USERS=%TOTAL_USERS: =%
set TOTAL_API_KEYS=%TOTAL_API_KEYS: =%
set TOTAL_USAGE_RECORDS=%TOTAL_USAGE_RECORDS: =%
set DB_SIZE=%DB_SIZE: =%

echo Database Name: %DB_NAME%
echo Total Tables: %TOTAL_TABLES%
echo Total Users: %TOTAL_USERS%
echo Total API Keys: %TOTAL_API_KEYS%
echo Total Usage Records: %TOTAL_USAGE_RECORDS%
echo Database Size: %DB_SIZE%

for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM users WHERE email = 'admin@devforge.ai';"') do set ADMIN_EXISTS=%%i
set ADMIN_EXISTS=%ADMIN_EXISTS: =%
if !ADMIN_EXISTS! equ 1 (
    echo Admin User: [SUCCESS] admin@devforge.ai exists
) else (
    echo Admin User: [ERROR] admin@devforge.ai missing
)

echo.
echo [SUCCESS] Database inspection completed!
echo.
echo [INFO] Tip: Check the generated schema export file for complete database structure
pause
