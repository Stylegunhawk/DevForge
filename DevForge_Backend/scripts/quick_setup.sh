#!/bin/bash

# DevForge Quick Database Setup
# For isolated PostgreSQL Docker environments
# Usage: ./quick_setup.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Database connection details
DB_CONTAINER="devforge-postgres"
DB_USER="devforge"
DB_NAME="devforge"

echo -e "${BLUE}🚀 DevForge Quick Database Setup${NC}"
echo -e "${BLUE}===================================${NC}"

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

# Check current tables
echo -e "\n${YELLOW}📊 Checking Current Tables${NC}"
CURRENT_TABLES=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
echo -e "${GREEN}Current tables: $CURRENT_TABLES${NC}"

if [ "$CURRENT_TABLES" -gt 0 ]; then
    echo -e "\n${YELLOW}📋 Current tables:${NC}"
    docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
    
    echo -e "\n${YELLOW}⚠️  Tables already exist! Choose an option:${NC}"
    echo "1) Drop all tables and recreate (DESTRUCTIVE)"
    echo "2) Keep existing tables and just apply enhancements"
    echo "3) Exit without changes"
    
    read -p "Enter your choice (1-3): " choice
    
    case $choice in
        1)
            echo -e "\n${RED}🗑️  Dropping all tables...${NC}"
            docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
COMMENT ON SCHEMA public IS 'standard public schema';
EOF
            echo -e "${GREEN}✅ All tables dropped${NC}"
            ;;
        2)
            echo -e "\n${YELLOW}🔧 Applying enhancements only...${NC}"
            docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < scripts/migrate_production_corrected.sql
            echo -e "${GREEN}✅ Enhancements applied${NC}"
            echo -e "\n${BLUE}🎉 Setup completed! Run quick_postgres_check.sh to verify.${NC}"
            exit 0
            ;;
        3)
            echo -e "\n${YELLOW}👋 Exiting without changes${NC}"
            exit 0
            ;;
        *)
            echo -e "\n${RED}❌ Invalid choice${NC}"
            exit 1
            ;;
    esac
fi

# Apply initial schema
echo -e "\n${YELLOW}🏗️  Creating initial database schema...${NC}"
docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < scripts/create_initial_schema.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Initial schema created successfully${NC}"
else
    echo -e "${RED}❌ Schema creation failed${NC}"
    exit 1
fi

# Verify tables were created
echo -e "\n${YELLOW}📋 Verifying created tables:${NC}"
TABLE_COUNT=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
echo -e "${GREEN}Total tables created: $TABLE_COUNT${NC}"

echo -e "\n${BLUE}📊 Table Overview:${NC}"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Check for admin user
echo -e "\n${YELLOW}👤 Checking admin user:${NC}"
ADMIN_EXISTS=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM users WHERE email = 'admin@devforge.ai';" | tr -d ' ')
if [ "$ADMIN_EXISTS" -eq 1 ]; then
    echo -e "${GREEN}✅ Admin user exists: admin@devforge.ai${NC}"
else
    echo -e "${YELLOW}⚠️  Admin user not found${NC}"
fi

# Check tier configuration
echo -e "\n${YELLOW}⚙️  Checking tier configuration:${NC}"
docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "SELECT tier, hourly_limit, monthly_limit, cost_per_1k_tokens FROM tier_config ORDER BY tier;"

echo -e "\n${GREEN}🎉 DevForge database setup completed successfully!${NC}"
echo -e "\n${BLUE}📋 Next steps:${NC}"
echo "1. Run './scripts/quick_postgres_check.sh' to verify the setup"
echo "2. Start your backend application"
echo "3. Login with admin@devforge.ai (password: adminpass123)"
echo -e "\n${BLUE}📚 Useful commands:${NC}"
echo "- Quick check: ./scripts/quick_postgres_check.sh"
echo "- Full inspection: ./scripts/postgres_inspection.sh"
echo "- Connect to DB: docker exec -it $DB_CONTAINER psql -U $DB_USER -d $DB_NAME"
