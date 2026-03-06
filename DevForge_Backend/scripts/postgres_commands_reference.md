# DevForge PostgreSQL Docker Commands Reference
# Comprehensive commands for database inspection and management

## 🚀 Quick Start Commands

### Start PostgreSQL Container
```bash
# Start only PostgreSQL
docker-compose up -d postgres

# Start all services
docker-compose up -d

# Check if PostgreSQL is running
docker ps | grep postgres
```

### Basic Connection Commands
```bash
# Connect to PostgreSQL shell
docker exec -it devforge-postgres psql -U devforge -d devforge

# Execute single SQL command
docker exec devforge-postgres psql -U devforge -d devforge -c "SELECT version();"

# Execute SQL from file
docker exec -i devforge-postgres psql -U devforge -d devforge < your_script.sql
```

## 📊 Database Inspection Commands

### Database Overview
```bash
# List all databases
docker exec devforge-postgres psql -U devforge -l

# Show database size
docker exec devforge-postgres psql -U devforge -d devforge -c "SELECT pg_size_pretty(pg_database_size('devforge'));"

# Show all tables
docker exec devforge-postgres psql -U devforge -d devforge -c "\dt"

# Show table details
docker exec devforge-postgres psql -U devforge -d devforge -c "\dt+"

# Show all indexes
docker exec devforge-postgres psql -U devforge -d devforge -c "\di"

# Show all functions
docker exec devforge-postgres psql -U devforge -d devforge -c "\df"
```

### Table Structure Analysis
```bash
# Describe specific table
docker exec devforge-postgres psql -U devforge -d devforge -c "\d users"

# Show table columns with types
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
ORDER BY ordinal_position;"

# Show table constraints
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    constraint_name,
    constraint_type,
    column_name
FROM information_schema.key_column_usage kcu
JOIN information_schema.table_constraints tc 
    ON kcu.constraint_name = tc.constraint_name
WHERE tc.table_name = 'users';"
```

### Data Analysis Commands
```bash
# Count rows in all tables
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    schemaname,
    tablename,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY live_rows DESC;"

# Show table sizes
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Show most recent data
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    'users' as table_name,
    COUNT(*) as total_rows,
    MAX(created_at) as latest_record
FROM users
UNION ALL
SELECT 
    'api_keys' as table_name,
    COUNT(*) as total_rows,
    MAX(created_at) as latest_record
FROM api_keys
UNION ALL
SELECT 
    'usage_analytics' as table_name,
    COUNT(*) as total_rows,
    MAX(created_at) as latest_record
FROM usage_analytics;"
```

## 🔍 Specific Table Queries

### Users Table Analysis
```bash
# User statistics
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    COUNT(*) as total_users,
    COUNT(CASE WHEN is_admin = true THEN 1 END) as admin_users,
    COUNT(CASE WHEN is_active = true THEN 1 END) as active_users,
    COUNT(CASE WHEN auth_provider = 'google' THEN 1 END) as google_users,
    COUNT(CASE WHEN auth_provider = 'local' THEN 1 END) as local_users
FROM users;"

# Recent user registrations
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    email,
    name,
    is_admin,
    auth_provider,
    created_at
FROM users
ORDER BY created_at DESC
LIMIT 10;"

# User login activity
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    email,
    last_login_at,
    created_at,
    CASE 
        WHEN last_login_at > NOW() - INTERVAL '7 days' THEN 'Active'
        WHEN last_login_at > NOW() - INTERVAL '30 days' THEN 'Recent'
        ELSE 'Inactive'
    END as activity_status
FROM users
ORDER BY last_login_at DESC NULLS LAST
LIMIT 20;"
```

### API Keys Analysis
```bash
# API key distribution by tier
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    tier,
    COUNT(*) as total_keys,
    COUNT(CASE WHEN is_active = true THEN 1 END) as active_keys,
    COUNT(CASE WHEN hourly_limit_override IS NOT NULL THEN 1 END) as hourly_overrides,
    COUNT(CASE WHEN monthly_limit_override IS NOT NULL THEN 1 END) as monthly_overrides
FROM api_keys
GROUP BY tier
ORDER BY tier;"

# Most used API keys
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    ak.id,
    ak.name,
    ak.tier,
    ak.usage_count,
    ak.last_used_at,
    u.email as user_email
FROM api_keys ak
LEFT JOIN users u ON ak.user_id = u.id
ORDER BY ak.usage_count DESC
LIMIT 10;"

# API keys with overrides
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    ak.name,
    ak.tier,
    ak.hourly_limit_override,
    ak.monthly_limit_override,
    tc.hourly_limit as tier_hourly,
    tc.monthly_limit as tier_monthly,
    u.email as user_email
FROM api_keys ak
JOIN tier_config tc ON ak.tier = tc.tier
LEFT JOIN users u ON ak.user_id = u.id
WHERE ak.hourly_limit_override IS NOT NULL OR ak.monthly_limit_override IS NOT NULL
ORDER BY ak.created_at DESC;"
```

### Usage Analytics
```bash
# Usage statistics by time period
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    DATE_TRUNC('day', created_at) as date,
    COUNT(*) as requests,
    COUNT(DISTINCT api_key_id) as unique_keys,
    SUM(tokens_used) as total_tokens,
    AVG(response_time_ms) as avg_response_time
FROM usage_analytics
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;"

# Top endpoints by usage
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    endpoint,
    method,
    COUNT(*) as request_count,
    SUM(tokens_used) as total_tokens,
    AVG(response_time_ms) as avg_response_time,
    COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count
FROM usage_analytics
WHERE created_at >= CURRENT_DATE - INTERVAL '24 hours'
GROUP BY endpoint, method
ORDER BY request_count DESC
LIMIT 10;"

# Error analysis
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    status_code,
    COUNT(*) as count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage,
    MIN(created_at) as first_occurrence,
    MAX(created_at) as last_occurrence
FROM usage_analytics
WHERE status_code >= 400
GROUP BY status_code
ORDER BY count DESC;"
```

## 🔧 Database Management Commands

### Backup and Restore
```bash
# Create full backup
docker exec devforge-postgres pg_dump -U devforge -d devforge > backup_$(date +%Y%m%d_%H%M%S).sql

# Create schema-only backup
docker exec devforge-postgres pg_dump -U devforge -d devforge --schema-only > schema_$(date +%Y%m%d_%H%M%S).sql

# Create data-only backup
docker exec devforge-postgres pg_dump -U devforge -d devforge --data-only > data_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
docker exec -i devforge-postgres psql -U devforge -d devforge < backup_file.sql

# Backup specific table
docker exec devforge-postgres pg_dump -U devforge -d devforge -t users > users_backup.sql
```

### Performance Analysis
```bash
# Show slow queries (requires pg_stat_statements extension)
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    rows
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;"

# Show table statistics
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    n_tup_ins,
    n_tup_upd,
    n_tup_del
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY seq_scan + idx_scan DESC;"

# Show index usage
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;"
```

### Maintenance Commands
```bash
# Vacuum analyze all tables
docker exec devforge-postgres psql -U devforge -d devforge -c "VACUUM ANALYZE;"

# Reindex database
docker exec devforge-postgres psql -U devforge -d devforge -c "REINDEX DATABASE devforge;"

# Update table statistics
docker exec devforge-postgres psql -U devforge -d devforge -c "ANALYZE;"

# Check database size before and after cleanup
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    pg_size_pretty(pg_database_size('devforge')) as database_size,
    pg_size_pretty(pg_total_relation_size('usage_analytics')) as usage_analytics_size;"
```

## 🚨 Troubleshooting Commands

### Connection Issues
```bash
# Test connection
docker exec devforge-postgres pg_isready -U devforge

# Check PostgreSQL logs
docker logs devforge-postgres --tail 50

# Check active connections
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    state_change
FROM pg_stat_activity
ORDER BY query_start;"

# Kill idle connections
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND query_start < NOW() - INTERVAL '1 hour';"
```

### Data Integrity Checks
```bash
# Check for orphaned records
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    'api_keys with missing users' as check_type,
    COUNT(*) as count
FROM api_keys ak
LEFT JOIN users u ON ak.user_id = u.id
WHERE ak.user_id IS NOT NULL AND u.id IS NULL

UNION ALL

SELECT 
    'usage_analytics with missing api_keys' as check_type,
    COUNT(*) as count
FROM usage_analytics ua
LEFT JOIN api_keys ak ON ua.api_key_id = ak.id
WHERE ak.id IS NULL;"

# Check data consistency
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    'API keys with invalid tier' as check_type,
    COUNT(*) as count
FROM api_keys ak
LEFT JOIN tier_config tc ON ak.tier = tc.tier
WHERE tc.tier IS NULL;"

# Check for duplicate data
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    'Duplicate email addresses' as check_type,
    email,
    COUNT(*) as count
FROM users
GROUP BY email
HAVING COUNT(*) > 1;"
```

## 📋 Running the Inspection Scripts

### Comprehensive Inspection
```bash
# Run the full inspection script
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
./scripts/postgres_inspection.sh
```

### Quick Check
```bash
# Run the quick check script
cd /Users/siddesh.kale/Documents/DevForge/DevForge_Backend
./scripts/quick_postgres_check.sh
```

### Apply Migration
```bash
# Apply the production migration
docker exec -i devforge-postgres psql -U devforge -d devforge < scripts/migrate_production.sql
```

## 🎯 Common Use Cases

### Before Deployment
```bash
# Check database health
./scripts/quick_postgres_check.sh

# Verify all tables exist
docker exec devforge-postgres psql -U devforge -d devforge -c "\dt"

# Check for missing indexes
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct
FROM pg_stats
WHERE schemaname = 'public'
AND n_distinct > 100
ORDER BY n_distinct DESC;"
```

### After Migration
```bash
# Verify migration success
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;"

# Check row counts
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    tablename,
    n_live_tup as rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY tablename;"
```

### Performance Monitoring
```bash
# Monitor slow queries
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
WHERE mean_time > 1000
ORDER BY mean_time DESC;"

# Check table bloat
docker exec devforge-postgres psql -U devforge -d devforge -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

This comprehensive reference covers all common PostgreSQL operations for DevForge database management and inspection.
