-- DevForge Backend Production Migration Script (CORRECTED)
-- Migration for existing database schema
-- Version: 1.0.1 (Corrected for current schema)
-- Date: 2026-03-06
-- 
-- This migration ADDS missing features to EXISTING tables
-- It does NOT recreate existing tables to preserve data

-- Enable UUID extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types if they don't exist
DO $$ BEGIN
    CREATE TYPE auth_provider_enum AS ENUM ('local', 'google');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('user', 'admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE tier_enum AS ENUM ('free', 'pro', 'enterprise');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE key_status_enum AS ENUM ('active', 'inactive', 'revoked');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ========================================
-- ALTER EXISTING TABLES
-- ========================================

-- Add missing columns to users table
DO $$
BEGIN
    -- Check if last_login_at column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'last_login_at'
    ) THEN
        ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE 'Added last_login_at column to users table';
    END IF;
    
    -- Check if updated_at column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE users ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT now();
        RAISE NOTICE 'Added updated_at column to users table';
    END IF;
END $$;

-- Add missing columns to api_keys table
DO $$
BEGIN
    -- Check if description column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'api_keys' AND column_name = 'description'
    ) THEN
        ALTER TABLE api_keys ADD COLUMN description TEXT;
        RAISE NOTICE 'Added description column to api_keys table';
    END IF;
    
    -- Check if status column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'api_keys' AND column_name = 'status'
    ) THEN
        ALTER TABLE api_keys ADD COLUMN status key_status_enum DEFAULT 'active';
        RAISE NOTICE 'Added status column to api_keys table';
    END IF;
    
    -- Check if usage_count column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'api_keys' AND column_name = 'usage_count'
    ) THEN
        ALTER TABLE api_keys ADD COLUMN usage_count INTEGER DEFAULT 0;
        RAISE NOTICE 'Added usage_count column to api_keys table';
    END IF;
    
    -- Add constraints for overrides if they don't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints 
        WHERE constraint_name = 'check_hourly_override'
    ) THEN
        ALTER TABLE api_keys ADD CONSTRAINT check_hourly_override 
            CHECK (hourly_limit_override IS NULL OR (hourly_limit_override > 0 AND hourly_limit_override <= 10000));
        RAISE NOTICE 'Added hourly_override constraint to api_keys table';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints 
        WHERE constraint_name = 'check_monthly_override'
    ) THEN
        ALTER TABLE api_keys ADD CONSTRAINT check_monthly_override 
            CHECK (monthly_limit_override IS NULL OR (monthly_limit_override > 0 AND monthly_limit_override <= 1000000));
        RAISE NOTICE 'Added monthly_override constraint to api_keys table';
    END IF;
END $$;

-- ========================================
-- CREATE NEW TABLES (if they don't exist)
-- ========================================

-- Create tenant_config table for RAG functionality
CREATE TABLE IF NOT EXISTS tenant_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id TEXT UNIQUE NOT NULL,
    tenant_name TEXT NOT NULL,
    mongodb_id TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    is_active BOOLEAN DEFAULT true,
    settings JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id)
);

-- Create rate_limit_cache table for Redis fallback
CREATE TABLE IF NOT EXISTS rate_limit_cache (
    key_id UUID REFERENCES api_keys(id) ON DELETE CASCADE,
    window_type TEXT NOT NULL, -- 'hourly' or 'monthly'
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    request_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    PRIMARY KEY (key_id, window_type, window_start)
);

-- Create audit_log table for tracking changes
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name TEXT NOT NULL,
    record_id UUID,
    action TEXT NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    old_values JSONB,
    new_values JSONB,
    changed_fields TEXT[],
    user_id UUID REFERENCES users(id),
    tenant_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    ip_address INET,
    user_agent TEXT
);

-- Create user_sessions table for session management
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token TEXT UNIQUE NOT NULL,
    refresh_token TEXT UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    ip_address INET,
    user_agent TEXT,
    is_active BOOLEAN DEFAULT true
);

-- ========================================
-- UPDATE TIER CONFIG (if needed)
-- ========================================

-- Ensure tier_config has proper enum type and updated_by column
DO $$
BEGIN
    -- Check if tier column needs to be converted to enum
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tier_config' AND column_name = 'tier' AND data_type != 'USER-DEFINED'
    ) THEN
        -- This would require manual intervention as column type conversion is complex
        RAISE NOTICE 'tier_config.tier column type conversion may be needed manually';
    END IF;
    
    -- Check if updated_by column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tier_config' AND column_name = 'updated_by'
    ) THEN
        ALTER TABLE tier_config ADD COLUMN updated_by UUID REFERENCES users(id);
        RAISE NOTICE 'Added updated_by column to tier_config table';
    END IF;
END $$;

-- ========================================
-- CREATE MISSING INDEXES
-- ========================================

-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_users_updated_at ON users(updated_at);
CREATE INDEX IF NOT EXISTS idx_users_last_login_at ON users(last_login_at);

-- API keys table indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status);
CREATE INDEX IF NOT EXISTS idx_api_keys_description ON api_keys(description);
CREATE INDEX IF NOT EXISTS idx_api_keys_usage_count ON api_keys(usage_count);

-- Request logs table indexes (additional performance indexes)
CREATE INDEX IF NOT EXISTS idx_request_logs_success ON request_logs(success);
CREATE INDEX IF NOT EXISTS idx_request_logs_duration_ms ON request_logs(duration_ms);

-- LLM usage table indexes (additional performance indexes)
CREATE INDEX IF NOT EXISTS idx_llm_usage_created_at ON llm_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_usage_task_type ON llm_usage(task_type);
CREATE INDEX IF NOT EXISTS idx_llm_usage_model_name ON llm_usage(model_name);

-- Monthly usage table indexes (additional performance indexes)
CREATE INDEX IF NOT EXISTS idx_monthly_usage_tokens_used ON monthly_usage(tokens_used);

-- RAG vectors table indexes (additional performance indexes)
CREATE INDEX IF NOT EXISTS idx_rag_vectors_created_at ON rag_vectors(created_at);
CREATE INDEX IF NOT EXISTS idx_rag_vectors_collection_name ON rag_vectors(collection_name);

-- New table indexes
CREATE INDEX IF NOT EXISTS idx_rate_limit_cache_expires_at ON rate_limit_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_rate_limit_cache_key_id_window_type ON rate_limit_cache(key_id, window_type);

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_table_name ON audit_log(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_record_id ON audit_log(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);

-- User sessions indexes
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

-- ========================================
-- CREATE FUNCTIONS AND TRIGGERS
-- ========================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers to tables that have the column
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_api_keys_updated_at ON api_keys;
CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tier_config_updated_at ON tier_config;
CREATE TRIGGER update_tier_config_updated_at BEFORE UPDATE ON tier_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_rate_limit_cache_updated_at ON rate_limit_cache;
CREATE TRIGGER update_rate_limit_cache_updated_at BEFORE UPDATE ON rate_limit_cache FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- CREATE VIEWS FOR COMMON QUERIES
-- ========================================

-- View for active users with their API keys count
CREATE OR REPLACE VIEW active_users_summary AS
SELECT 
    u.id,
    u.email,
    u.name,
    u.is_admin,
    u.created_at,
    u.last_login_at,
    COUNT(ak.id) as api_keys_count,
    COUNT(CASE WHEN ak.is_active = true THEN 1 END) as active_keys_count
FROM users u
LEFT JOIN api_keys ak ON u.id = ak.user_id
WHERE u.is_active = true
GROUP BY u.id, u.email, u.name, u.is_admin, u.created_at, u.last_login_at;

-- View for tier usage statistics
CREATE OR REPLACE VIEW tier_usage_stats AS
SELECT 
    tc.tier,
    tc.hourly_limit,
    tc.monthly_limit,
    tc.cost_per_1k_tokens,
    tc.is_active,
    COUNT(ak.id) as total_keys,
    COUNT(CASE WHEN ak.is_active = true THEN 1 END) as active_keys,
    COUNT(CASE WHEN ak.hourly_limit_override IS NOT NULL OR ak.monthly_limit_override IS NOT NULL THEN 1 END) as keys_with_overrides
FROM tier_config tc
LEFT JOIN api_keys ak ON tc.tier = ak.tier
GROUP BY tc.tier, tc.hourly_limit, tc.monthly_limit, tc.cost_per_1k_tokens, tc.is_active
ORDER BY tc.tier;

-- View for recent API usage (using request_logs)
CREATE OR REPLACE VIEW recent_api_usage AS
SELECT 
    rl.id,
    ak.name as key_name,
    ak.tier,
    rl.user_id,
    u.email as user_email,
    rl.tenant_id,
    rl.tool_name as endpoint,
    rl.success as status_code,
    rl.duration_ms as response_time_ms,
    rl.created_at
FROM request_logs rl
JOIN api_keys ak ON rl.user_id = ak.user_id  -- Note: using user_id join since api_key_id may not exist
LEFT JOIN users u ON rl.user_id = u.id
WHERE rl.created_at >= now() - INTERVAL '24 hours'
ORDER BY rl.created_at DESC;

-- ========================================
-- CREATE STORED PROCEDURES
-- ========================================

-- Procedure to get user's API keys with usage stats
CREATE OR REPLACE FUNCTION get_user_api_keys(p_user_id UUID)
RETURNS TABLE (
    id UUID,
    name TEXT,
    integration_name TEXT,
    tier tier_enum,
    hourly_limit_override INTEGER,
    monthly_limit_override INTEGER,
    is_active BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ak.id,
        ak.name,
        ak.integration_name,
        ak.tier::text::tier_enum,  -- Cast text to enum
        ak.hourly_limit_override,
        ak.monthly_limit_override,
        ak.is_active,
        ak.created_at,
        ak.last_used_at,
        ak.usage_count
    FROM api_keys ak
    WHERE ak.user_id = p_user_id
    ORDER BY ak.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Procedure to update tier configuration with audit trail
CREATE OR REPLACE FUNCTION update_tier_config_with_audit(
    p_tier TEXT,  -- Use TEXT instead of enum for flexibility
    p_hourly_limit INTEGER,
    p_monthly_limit INTEGER DEFAULT NULL,
    p_cost_per_1k_tokens DECIMAL(10,6),
    p_max_expiry_days INTEGER DEFAULT 180,
    p_is_active BOOLEAN DEFAULT true,
    p_updated_by UUID DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    old_config JSONB;
    new_config JSONB;
BEGIN
    -- Get old configuration
    SELECT row_to_json(tc.*) INTO old_config
    FROM tier_config tc
    WHERE tc.tier = p_tier::tier_enum;
    
    -- Update configuration
    UPDATE tier_config SET
        hourly_limit = p_hourly_limit,
        monthly_limit = p_monthly_limit,
        cost_per_1k_tokens = p_cost_per_1k_tokens,
        max_expiry_days = p_max_expiry_days,
        is_active = p_is_active,
        updated_by = p_updated_by,
        updated_at = now()
    WHERE tier = p_tier::tier_enum;
    
    -- Get new configuration
    SELECT row_to_json(tc.*) INTO new_config
    FROM tier_config tc
    WHERE tc.tier = p_tier::tier_enum;
    
    -- Create audit log entry
    INSERT INTO audit_log (
        table_name, record_id, action, old_values, new_values, 
        changed_fields, user_id, created_at
    ) VALUES (
        'tier_config', p_tier, 'UPDATE', old_config, new_config,
        ARRAY['hourly_limit', 'monthly_limit', 'cost_per_1k_tokens', 'max_expiry_days', 'is_active'],
        p_updated_by, now()
    );
    
    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- CREATE DATABASE ROLES
-- ========================================

-- Application role with basic access
DO $$ BEGIN
    CREATE ROLE app_user;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Admin role with elevated access
DO $$ BEGIN
    CREATE ROLE app_admin;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Read-only role for analytics
DO $$ BEGIN
    CREATE ROLE app_readonly;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Grant permissions
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_user;

GRANT USAGE ON SCHEMA public TO app_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_admin;

GRANT USAGE ON SCHEMA public TO app_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

-- Grant permissions on views
GRANT SELECT ON active_users_summary TO app_readonly;
GRANT SELECT ON tier_usage_stats TO app_readonly;
GRANT SELECT ON recent_api_usage TO app_readonly;

-- ========================================
-- CLEANUP AND VERIFICATION
-- ========================================

-- Update statistics
ANALYZE;

-- Final verification queries
DO $$
BEGIN
    RAISE NOTICE '=== DevForge Production Migration (CORRECTED) Complete ===';
    RAISE NOTICE 'Added missing columns to existing tables';
    RAISE NOTICE 'Created new tables: tenant_config, rate_limit_cache, audit_log, user_sessions';
    RAISE NOTICE 'Added missing indexes for performance optimization';
    RAISE NOTICE 'Created views for common queries';
    RAISE NOTICE 'Created stored procedures for common operations';
    RAISE NOTICE 'Created database roles: app_user, app_admin, app_readonly';
    RAISE NOTICE 'Migration completed successfully on %', now();
END $$;
