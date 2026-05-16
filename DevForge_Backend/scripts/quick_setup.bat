@echo off
REM DevForge Quick Database Setup for Windows
REM For isolated PostgreSQL Docker environments
REM Usage: quick_setup.bat

setlocal enabledelayedexpansion

echo.
echo ========================================
echo    DevForge Quick Database Setup
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

REM Check current tables
echo.
echo [INFO] Checking Current Tables...
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"') do set CURRENT_TABLES=%%i
set CURRENT_TABLES=%CURRENT_TABLES: =%
echo [INFO] Current tables: %CURRENT_TABLES%

if %CURRENT_TABLES% gtr 0 (
    echo.
    echo [INFO] Current tables:
    docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
    
    echo.
    echo [WARNING] Tables already exist! Choose an option:
    echo 1) Drop all tables and recreate (DESTRUCTIVE)
    echo 2) Keep existing tables and just apply enhancements
    echo 3) Exit without changes
    echo.
    set /p choice="Enter your choice (1-3): "
    
    if "!choice!"=="1" (
        echo.
        echo [INFO] Dropping all tables...
        docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public; COMMENT ON SCHEMA public IS 'standard public schema';"
        echo [SUCCESS] All tables dropped
    ) else if "!choice!"=="2" (
        echo.
        echo [INFO] Applying enhancements only...
        docker exec -i %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME < scripts\migrate_production_corrected.sql
        if %errorlevel% neq 0 (
            echo [ERROR] Enhancements failed
            pause
            exit /b 1
        )
        echo [SUCCESS] Enhancements applied
        echo.
        echo Setup completed! Run quick_postgres_check.bat to verify.
        pause
        exit /b 0
    ) else if "!choice!"=="3" (
        echo.
        echo [INFO] Exiting without changes
        pause
        exit /b 0
    ) else (
        echo.
        echo [ERROR] Invalid choice
        pause
        exit /b 1
    )
)

REM Apply initial schema
echo.
echo [INFO] Creating initial database schema...
docker exec -i %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME < scripts\create_initial_schema.sql
if %errorlevel% neq 0 (
    echo [ERROR] Schema creation failed
    pause
    exit /b 1
)
echo [SUCCESS] Initial schema created successfully

REM Verify tables were created
echo.
echo [INFO] Verifying created tables...
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"') do set TABLE_COUNT=%%i
set TABLE_COUNT=%TABLE_COUNT: =%
echo [INFO] Total tables created: %TABLE_COUNT%

echo.
echo [INFO] Table Overview:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

REM Check for admin user
echo.
echo [INFO] Checking admin user...
for /f "tokens=*" %%i in ('docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -t -c "SELECT COUNT(*) FROM users WHERE email = 'admin@devforge.ai';"') do set ADMIN_EXISTS=%%i
set ADMIN_EXISTS=%ADMIN_EXISTS: =%
if !ADMIN_EXISTS! equ 1 (
    echo [SUCCESS] Admin user exists: admin@devforge.ai
) else (
    echo [WARNING] Admin user not found
)

REM Check tier configuration
echo.
echo [INFO] Checking tier configuration:
docker exec %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME -c "SELECT tier, hourly_limit, monthly_limit, cost_per_1k_tokens FROM tier_config ORDER BY tier;"

echo.
echo [SUCCESS] DevForge database setup completed successfully!
echo.
echo Next steps:
echo 1. Run 'quick_postgres_check.bat' to verify the setup
echo 2. Start your backend application
echo 3. Login with admin@devforge.ai (password: adminpass123)
echo.
echo Useful commands:
echo - Quick check: quick_postgres_check.bat
echo - Full inspection: postgres_inspection.bat
echo - Connect to DB: docker exec -it %DB_CONTAINER% psql -U %DB_USER% -d %DB_NAME
echo.
pause
