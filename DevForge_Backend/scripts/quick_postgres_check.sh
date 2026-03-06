#!/bin/bash

# Quick PostgreSQL Inspection Commands
# Fast database overview commands
# Usage: ./quick_postgres_check.sh

set -e

# Database connection details
DB_CONTAINER="devforge-postgres"
DB_USER="devforge"
DB_NAME="devforge"

echo -e "🔍 Quick DevForge PostgreSQL Check"
echo -e "=================================="

# Check if container is running
if ! docker ps | grep -q $DB_CONTAINER; then
    echo "❌ PostgreSQL container not running"
    echo "Start with: docker-compose up -d postgres"
    exit 1
fi

echo "✅ PostgreSQL container is running"

# Quick stats
echo -e "\n📊 Quick Database Stats:"
echo "------------------------"

echo "Database Size:"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME')) as size;"

echo -e "\nTable Counts:"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    relname as tablename,
    n_live_tup as rows,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as size
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;"

echo -e "\n👥 Users & API Keys:"
echo "--------------------"
echo "Total Users:"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM users;"

echo "Admin Users:"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM users WHERE is_admin = true;"

echo "Active Users:"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM users WHERE is_active = true;"

echo "Total API Keys:"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM api_keys;"

echo "Active API Keys:"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM api_keys WHERE is_active = true;"

echo -e "\n⚙️ Tier Configuration:"
echo "----------------------"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    tier,
    hourly_limit,
    monthly_limit,
    cost_per_1k_tokens,
    is_active
FROM tier_config
ORDER BY tier;"

echo -e "\n📈 Recent Usage (Last 24h):"
echo "-----------------------------"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    COUNT(*) as total_requests,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(CASE WHEN success = false THEN 1 END) as errors
FROM request_logs
WHERE created_at >= NOW() - INTERVAL '24 hours';"

echo -e "\n🔑 API Keys with Overrides:"
echo "---------------------------"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    ak.name,
    ak.tier,
    ak.hourly_limit_override,
    ak.monthly_limit_override,
    u.email as user_email
FROM api_keys ak
LEFT JOIN users u ON ak.user_id = u.id
WHERE ak.hourly_limit_override IS NOT NULL OR ak.monthly_limit_override IS NOT NULL
ORDER BY ak.created_at DESC;"

echo -e "\n✅ Quick check completed!"
