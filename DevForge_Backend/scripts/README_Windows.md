# DevForge Database Setup - Windows

## 🚀 Quick Start for Windows

### Prerequisites
- Docker Desktop installed and running
- PostgreSQL container named `devforge-postgres`
- Database name: `devforge`
- User: `devforge`

### 📋 Available Scripts

#### 1. Quick Setup (Recommended for first time)
```cmd
# Automated setup with interactive options
quick_setup.bat
```

#### 2. Quick Health Check
```cmd
# 2-minute database overview
quick_postgres_check.bat
```

#### 3. Comprehensive Inspection
```cmd
# 5-minute detailed analysis
postgres_inspection.bat
```

### 🎯 Usage Scenarios

#### Scenario 1: Fresh Database
```cmd
# Run automated setup
quick_setup.bat
# Choose option 1 (or press enter if no tables exist)
```

#### Scenario 2: Existing Tables
```cmd
# Run setup and choose your option
quick_setup.bat
# 1 = Fresh start (destructive)
# 2 = Add enhancements only
# 3 = Exit without changes
```

#### Scenario 3: Verify Setup
```cmd
# Quick verification
quick_postgres_check.bat

# Full inspection
postgres_inspection.bat
```

### 📊 Expected Results

After successful setup, you should have:
- **11 tables** total
- **Default admin user**: `admin@devforge.ai`
- **3 tier configurations**: free, pro, enterprise
- **25+ performance indexes**

### 🔧 Manual Commands

#### Connect to Database
```cmd
docker exec -it devforge-postgres psql -U devforge -d devforge
```

#### Apply Schema Manually
```cmd
docker exec -i devforge-postgres psql -U devforge -d devforge < scripts\create_initial_schema.sql
```

#### Apply Enhancements Only
```cmd
docker exec -i devforge-postgres psql -U devforge -d devforge < scripts\migrate_production_corrected.sql
```

### 🛠️ Troubleshooting

#### Container Not Running
```cmd
# Start PostgreSQL
docker-compose up -d postgres

# Check status
docker ps | findstr devforge-postgres
```

#### Connection Issues
```cmd
# Test connection
docker exec devforge-postgres psql -U devforge -d devforge -c "SELECT 1;"
```

#### Permission Issues
```cmd
# Make sure scripts are in the correct path
cd C:\path\to\DevForge_Backend\scripts
quick_setup.bat
```

### 📁 File Structure
```
DevForge_Backend/
├── scripts/
│   ├── quick_setup.bat                 # Main setup script
│   ├── quick_postgres_check.bat        # Quick verification
│   ├── postgres_inspection.bat         # Full inspection
│   ├── create_initial_schema.sql       # Complete schema
│   └── migrate_production_corrected.sql # Enhancements only
└── tests/
    └── hello.py                        # Test file
```

### 🎉 After Setup

1. **Verify setup**: `quick_postgres_check.bat`
2. **Start backend**: Your DevForge backend application
3. **Login**: Use `admin@devforge.ai` with password `adminpass123`
4. **Monitor**: Use inspection scripts to check database health

### 📞 Support

If you encounter issues:
1. Check Docker Desktop is running
2. Verify PostgreSQL container status
3. Run connection test commands
4. Check script permissions and paths

All scripts are designed to be **Windows-compatible** with proper error handling and user-friendly output!
