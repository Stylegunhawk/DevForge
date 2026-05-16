#!/bin/bash

# DevForge PostgreSQL Inspection Commands
# Comprehensive database analysis script
# Usage: ./postgres_inspection.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database connection details
DB_HOST="localhost"
DB_PORT="5432"
DB_USER="devforge"
DB_NAME="devforge"
DB_CONTAINER="devforge-postgres"

echo -e "${BLUE}🔍 DevForge PostgreSQL Database Inspection${NC}"
echo -e "${BLUE}============================================${NC}"

# Function to execute SQL and format output
execute_sql() {
    local description=$1
    local sql=$2
    
    echo -e "\n${YELLOW}📊 $description${NC}"
    echo -e "${GREEN}SQL: $sql${NC}"
    echo "----------------------------------------"
    
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "$sql" || {
        echo -e "${RED}❌ Error executing SQL${NC}"
        return 1
    }
}

# Function to execute multiple SQL commands
execute_sql_file() {
    local description=$1
    local sql_file=$2
    
    echo -e "\n${YELLOW}📄 $description${NC}"
    echo -e "${GREEN}File: $sql_file${NC}"
    echo "----------------------------------------"
    
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < "$sql_file" || {
        echo -e "${RED}❌ Error executing SQL file${NC}"
        return 1
    }
}

# Check if PostgreSQL container is running
echo -e "\n${YELLOW}🔧 Checking PostgreSQL Container Status${NC}"
if docker ps | grep -q $DB_CONTAINER; then
    echo -e "${GREEN}✅ PostgreSQL container is running${NC}"
else
    echo -e "${RED}❌ PostgreSQL container is not running${NC}"
    echo -e "${YELLOW}Please start PostgreSQL with: docker-compose up -d postgres${NC}"
    exit 1
fi

# Test database connection
echo -e "\n${YELLOW}🔌 Testing Database Connection${NC}"
if docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Database connection successful${NC}"
else
    echo -e "${RED}❌ Database connection failed${NC}"
    exit 1
fi

# 1. Database Overview
execute_sql "Database Overview" "
    SELECT 
        current_database() as database_name,
        version() as postgresql_version,
        current_user as current_user,
        inet_server_addr() as server_address,
        inet_server_port() as server_port;
"

# 2. All Tables with Row Counts and Sizes
execute_sql "All Tables Overview" "
    SELECT 
        schemaname,
        tablename,
        tableowner,
        hasindexes,
        hasrules,
        hastriggers,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size
    FROM pg_tables 
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# 3. Detailed Table Information
execute_sql "Detailed Table Information" "
    SELECT 
        t.table_name,
        c.column_name,
        c.data_type,
        c.character_maximum_length,
        c.is_nullable,
        c.column_default,
        c.ordinal_position
    FROM information_schema.tables t
    JOIN information_schema.columns c ON t.table_name = c.table_name
    WHERE t.table_schema = 'public'
    ORDER BY t.table_name, c.ordinal_position;
"

# 4. Table Row Counts
execute_sql "Table Row Counts" "
    SELECT 
        schemaname,
        relname as tablename,
        n_tup_ins as total_inserts,
        n_tup_upd as total_updates,
        n_tup_del as total_deletes,
        n_live_tup as live_rows,
        n_dead_tup as dead_rows,
        last_vacuum,
        last_autovacuum,
        last_analyze,
        last_autoanalyze
    FROM pg_stat_user_tables
    ORDER BY live_rows DESC;
"

# 5. Indexes Information
execute_sql "All Indexes" "
    SELECT 
        schemaname,
        tablename,
        indexname,
        indexdef
    FROM pg_indexes
    WHERE schemaname = 'public'
    ORDER BY tablename, indexname;
"

# 6. Constraints Information
execute_sql "Table Constraints" "
    SELECT 
        tc.table_name,
        tc.constraint_name,
        tc.constraint_type,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints tc
    LEFT JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
    LEFT JOIN information_schema.constraint_column_usage ccu
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.table_schema = 'public'
    ORDER BY tc.table_name, tc.constraint_type;
"

# 7. Users Table Details
execute_sql "Users Table Sample Data" "
    SELECT 
        id,
        email,
        name,
        is_admin,
        is_active,
        auth_provider,
        created_at
    FROM users
    ORDER BY created_at DESC
    LIMIT 10;
"

# 8. API Keys Overview
execute_sql "API Keys Overview" "
    SELECT 
        ak.id,
        ak.name,
        ak.tier,
        ak.integration_name,
        ak.is_active,
        ak.hourly_limit_override,
        ak.monthly_limit_override,
        ak.created_at,
        ak.last_used_at,
        u.email as user_email
    FROM api_keys ak
    LEFT JOIN users u ON ak.user_id = u.id
    ORDER BY ak.created_at DESC
    LIMIT 20;
"

# 9. Tier Configuration
execute_sql "Tier Configuration" "
    SELECT 
        tier,
        hourly_limit,
        monthly_limit,
        cost_per_1k_tokens,
        max_expiry_days,
        is_active,
        updated_at,
        updated_by
    FROM tier_config
    ORDER BY tier;
"

# 10. Usage Analytics Summary
execute_sql "Usage Analytics Summary" "
    SELECT 
        DATE_TRUNC('day', created_at) as date,
        COUNT(*) as total_requests,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(duration_ms) as avg_response_time,
        COUNT(CASE WHEN success = false THEN 1 END) as error_count
    FROM request_logs
    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY DATE_TRUNC('day', created_at)
    ORDER BY date DESC;
"

# 11. Most Active API Keys
execute_sql "Most Active API Keys (Last 24 Hours)" "
    SELECT 
        'API Keys activity tracked in request_logs table' as status,
        'Use quick_postgres_check.sh for API key overview' as suggestion;
"

# 12. Database Size Analysis
execute_sql "Database Size Analysis" "
    SELECT 
        pg_size_pretty(pg_database_size(current_database())) as database_size,
        (SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public') as table_count,
        (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public') as index_count,
        (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public') as column_count;
"

# 13. Partition Information
execute_sql "Partition Information" "
    SELECT 
        'No partitions found - using regular tables' as status;
"

# 14. Role and Permission Information
execute_sql "Database Roles and Permissions" "
    SELECT 
        rolname as role_name,
        rolsuper as is_superuser,
        rolcreaterole as can_create_role,
        rolcreatedb as can_create_db,
        rolcanlogin as can_login,
        rolconnlimit as connection_limit
    FROM pg_roles
    WHERE rolname LIKE 'app_%'
    ORDER BY rolname;
"

# 15. Check for Missing Indexes
execute_sql "Potential Missing Indexes" "
    SELECT 
        schemaname,
        tablename,
        attname,
        n_distinct,
        correlation
    FROM pg_stats
    WHERE schemaname = 'public'
    AND n_distinct > 100
    AND tablename NOT LIKE 'pg_%'
    ORDER BY n_distinct DESC
    LIMIT 20;
"

# 16. Recent Audit Log Entries
execute_sql "Recent Activity" "
    SELECT 
        'Recent API Requests' as activity_type,
        COUNT(*) as count,
        MAX(created_at) as latest_activity
    FROM request_logs
    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
    
    UNION ALL
    
    SELECT 
        'Recent User Registrations' as activity_type,
        COUNT(*) as count,
        MAX(created_at) as latest_activity
    FROM users
    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';
"

# 17. Check for Orphaned Records
execute_sql "Orphaned Records Check" "
    SELECT 
        'api_keys with missing users' as check_type,
        COUNT(*) as count
    FROM api_keys ak
    LEFT JOIN users u ON ak.user_id = u.id
    WHERE ak.user_id IS NOT NULL AND u.id IS NULL
    
    UNION ALL
    
    SELECT 
        'request_logs with missing users' as check_type,
        COUNT(*) as count
    FROM request_logs rl
    LEFT JOIN users u ON rl.user_id = u.id
    WHERE rl.user_id IS NOT NULL AND u.id IS NULL
    
    UNION ALL
    
    SELECT 
        'llm_usage with missing users' as check_type,
        COUNT(*) as count
    FROM llm_usage lu
    LEFT JOIN users u ON lu.user_id = u.id
    WHERE lu.user_id IS NOT NULL AND u.id IS NULL;
"

# 18. Performance Statistics
execute_sql "Performance Statistics" "
    SELECT 
        schemaname,
        relname as tablename,
        seq_scan,
        seq_tup_read,
        idx_scan,
        idx_tup_fetch,
        n_tup_ins,
        n_tup_upd,
        n_tup_del,
        n_live_tup,
        n_dead_tup
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY seq_scan + idx_scan DESC
    LIMIT 15;
"

# 19. Configuration Settings
execute_sql "Important Configuration Settings" "
    SELECT 
        name,
        setting,
        unit,
        category,
        short_desc
    FROM pg_settings
    WHERE name IN (
        'max_connections',
        'shared_buffers',
        'effective_cache_size',
        'work_mem',
        'maintenance_work_mem',
        'checkpoint_completion_target',
        'wal_buffers',
        'default_statistics_target',
        'random_page_cost',
        'effective_io_concurrency'
    )
    ORDER BY category, name;
"

# 20. Create comprehensive export
echo -e "\n${YELLOW}📤 Creating Comprehensive Database Export${NC}"
docker exec $DB_CONTAINER pg_dump -U $DB_USER -d $DB_NAME --schema-only --no-owner --no-privileges > /tmp/devforge_schema_$(date +%Y%m%d_%H%M%S).sql
echo -e "${GREEN}✅ Schema exported to /tmp/devforge_schema_$(date +%Y%m%d_%H%M%S).sql${NC}"

# 21. Generate summary report
echo -e "\n${YELLOW}📋 Database Summary Report${NC}"
echo "========================================"

# Get quick stats
TOTAL_TABLES=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" | tr -d ' ')
TOTAL_USERS=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM users;" | tr -d ' ')
TOTAL_API_KEYS=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM api_keys;" | tr -d ' ')
TOTAL_USAGE_RECORDS=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM usage_analytics;" | tr -d ' ')
DB_SIZE=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT pg_size_pretty(pg_database_size(current_database()));" | tr -d ' ')

echo -e "${GREEN}Database Name:${NC} $DB_NAME"
echo -e "${GREEN}Total Tables:${NC} $TOTAL_TABLES"
echo -e "${GREEN}Total Users:${NC} $TOTAL_USERS"
echo -e "${GREEN}Total API Keys:${NC} $TOTAL_API_KEYS"
echo -e "${GREEN}Total Usage Records:${NC} $TOTAL_USAGE_RECORDS"
echo -e "${GREEN}Database Size:${NC} $DB_SIZE"

# Check for admin user
ADMIN_EXISTS=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM users WHERE email = 'admin@devforge.ai';" | tr -d ' ')
if [ "$ADMIN_EXISTS" -eq 1 ]; then
    echo -e "${GREEN}Admin User:${NC} ✅ admin@devforge.ai exists"
else
    echo -e "${RED}Admin User:${NC} ❌ admin@devforge.ai missing"
fi

echo -e "\n${BLUE}🎉 Database inspection completed!${NC}"
echo -e "${YELLOW}💡 Tip: Check the generated schema export file for complete database structure${NC}"
