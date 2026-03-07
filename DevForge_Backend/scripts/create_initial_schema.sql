-- DevForge Backend - Initial Database Schema Creation
-- Creates all core tables from scratch
-- Use this for fresh PostgreSQL installations
-- Version: 1.0.0
-- Date: 2026-03-07

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types
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
-- CORE TABLES
-- ========================================

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    name VARCHAR(255),
    avatar_url TEXT,
    is_admin BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    auth_provider VARCHAR(50) DEFAULT 'local',
    google_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    email_verified BOOLEAN DEFAULT false,
    email_verified_at TIMESTAMP WITH TIME ZONE
);

-- Tier configuration table
CREATE TABLE tier_config (
    tier tier_enum PRIMARY KEY,
    hourly_limit INTEGER NOT NULL,
    monthly_limit INTEGER,
    cost_per_1k_tokens NUMERIC(10,6) NOT NULL DEFAULT 0.01,
    max_expiry_days INTEGER DEFAULT 180,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID REFERENCES users(id)
);

-- API Keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_hash TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    integration_name TEXT NOT NULL,
    tier tier_enum DEFAULT 'free' NOT NULL,
    tenant_id TEXT NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    scopes JSONB DEFAULT '[]',
    hourly_limit_override INTEGER,
    monthly_limit_override INTEGER,
    is_active BOOLEAN DEFAULT true,
    status key_status_enum DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,
    expiry_duration TEXT,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),
    
    -- Constraints
    CONSTRAINT check_hourly_override CHECK (hourly_limit_override IS NULL OR (hourly_limit_override > 0 AND hourly_limit_override <= 10000)),
    CONSTRAINT check_monthly_override CHECK (monthly_limit_override IS NULL OR (monthly_limit_override > 0 AND monthly_limit_override <= 1000000))
);

-- Request logs table
CREATE TABLE request_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id TEXT NOT NULL,
    integration_name TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_summary TEXT,
    success BOOLEAN DEFAULT true,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- LLM usage table
CREATE TABLE llm_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL,
    integration_name VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

-- Monthly usage aggregation table
CREATE TABLE monthly_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    year_month TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    requests_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (api_key_id, year_month)
);

-- RAG vectors table (this might already exist)
CREATE TABLE IF NOT EXISTS rag_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chunk_id TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536), -- Adjust dimension based on your model
    source TEXT,
    tenant_id TEXT,
    collection_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- ENHANCEMENT TABLES
-- ========================================

-- Tenant configuration for RAG
CREATE TABLE tenant_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id TEXT UNIQUE NOT NULL,
    tenant_name TEXT NOT NULL,
    mongodb_id TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    settings JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id)
);

-- Rate limit cache for Redis fallback
CREATE TABLE rate_limit_cache (
    key_id UUID REFERENCES api_keys(id) ON DELETE CASCADE,
    window_type TEXT NOT NULL, -- 'hourly' or 'monthly'
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    request_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    PRIMARY KEY (key_id, window_type, window_start)
);

-- Audit log for change tracking
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name TEXT NOT NULL,
    record_id UUID,
    action TEXT NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    old_values JSONB,
    new_values JSONB,
    changed_fields TEXT[],
    user_id UUID REFERENCES users(id),
    tenant_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

-- User sessions for authentication
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token TEXT UNIQUE NOT NULL,
    refresh_token TEXT UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    is_active BOOLEAN DEFAULT true
);

-- ========================================
-- INDEXES FOR PERFORMANCE
-- ========================================

-- Users table indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_updated_at ON users(updated_at);
CREATE INDEX idx_users_last_login_at ON users(last_login_at);

-- API keys table indexes
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_tenant_id ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_tier ON api_keys(tier);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_status ON api_keys(status);
CREATE INDEX idx_api_keys_created_at ON api_keys(created_at);
CREATE INDEX idx_api_keys_last_used_at ON api_keys(last_used_at);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_api_keys_integration ON api_keys(integration_name);

-- Request logs indexes
CREATE INDEX idx_request_logs_user_id ON request_logs(user_id);
CREATE INDEX idx_request_logs_tenant_id ON request_logs(tenant_id);
CREATE INDEX idx_request_logs_tool_name ON request_logs(tool_name);
CREATE INDEX idx_request_logs_created_at ON request_logs(created_at);
CREATE INDEX idx_request_logs_success ON request_logs(success);
CREATE INDEX idx_request_logs_dashboard ON request_logs(created_at, tool_name, success);
CREATE INDEX idx_request_logs_user_created ON request_logs(user_id, created_at DESC);

-- LLM usage indexes
CREATE INDEX idx_llm_usage_tenant ON llm_usage(tenant_id);
CREATE INDEX idx_llm_usage_integration ON llm_usage(integration_name);
CREATE INDEX idx_llm_usage_model_name ON llm_usage(model_name);
CREATE INDEX idx_llm_usage_task_type ON llm_usage(task_type);
CREATE INDEX idx_llm_usage_created_at ON llm_usage(created_at);
CREATE INDEX idx_llm_usage_user ON llm_usage(user_id);

-- Monthly usage indexes
CREATE INDEX idx_monthly_usage_key_month ON monthly_usage(api_key_id, year_month);
CREATE INDEX idx_monthly_usage_last_updated ON monthly_usage(last_updated);
CREATE INDEX idx_monthly_usage_tokens_used ON monthly_usage(tokens_used);

-- RAG vectors indexes
CREATE INDEX idx_rag_vectors_chunk_id ON rag_vectors(chunk_id);
CREATE INDEX idx_rag_vectors_embedding ON rag_vectors USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_rag_vectors_source ON rag_vectors(source);
CREATE INDEX idx_rag_vectors_tenant ON rag_vectors(tenant_id, collection_name);
CREATE INDEX idx_rag_vectors_created_at ON rag_vectors(created_at);

-- Enhancement table indexes
CREATE INDEX idx_rate_limit_cache_expires_at ON rate_limit_cache(expires_at);
CREATE INDEX idx_rate_limit_cache_key_window ON rate_limit_cache(key_id, window_type);

-- Audit log indexes
CREATE INDEX idx_audit_log_table_name ON audit_log(table_name);
CREATE INDEX idx_audit_log_record_id ON audit_log(record_id);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- User sessions indexes
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_session_token ON user_sessions(session_token);
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);

-- ========================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ========================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tier_config_updated_at BEFORE UPDATE ON tier_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_rate_limit_cache_updated_at BEFORE UPDATE ON rate_limit_cache FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- VIEWS FOR COMMON QUERIES
-- ========================================

-- Active users summary
CREATE VIEW active_users_summary AS
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

-- Tier usage statistics
CREATE VIEW tier_usage_stats AS
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

-- Recent API usage
CREATE VIEW recent_api_usage AS
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
LEFT JOIN api_keys ak ON rl.user_id = ak.user_id
LEFT JOIN users u ON rl.user_id = u.id
WHERE rl.created_at >= now() - INTERVAL '24 hours'
ORDER BY rl.created_at DESC;

-- ========================================
-- STORED PROCEDURES
-- ========================================

-- Get user's API keys with usage stats
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
        ak.tier,
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

-- Update tier configuration with audit trail
CREATE OR REPLACE FUNCTION update_tier_config_with_audit(
    p_tier tier_enum,
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
    WHERE tc.tier = p_tier;
    
    -- Update configuration
    UPDATE tier_config SET
        hourly_limit = p_hourly_limit,
        monthly_limit = p_monthly_limit,
        cost_per_1k_tokens = p_cost_per_1k_tokens,
        max_expiry_days = p_max_expiry_days,
        is_active = p_is_active,
        updated_by = p_updated_by,
        updated_at = now()
    WHERE tier = p_tier;
    
    -- Get new configuration
    SELECT row_to_json(tc.*) INTO new_config
    FROM tier_config tc
    WHERE tc.tier = p_tier;
    
    -- Create audit log entry
    INSERT INTO audit_log (
        table_name, record_id, action, old_values, new_values, 
        changed_fields, user_id, created_at
    ) VALUES (
        'tier_config', p_tier::text, 'UPDATE', old_config, new_config,
        ARRAY['hourly_limit', 'monthly_limit', 'cost_per_1k_tokens', 'max_expiry_days', 'is_active'],
        p_updated_by, now()
    );
    
    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- DATABASE ROLES AND PERMISSIONS
-- ========================================

-- Application roles
DO $$ BEGIN
    CREATE ROLE app_user;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE ROLE app_admin;
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

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
-- INITIAL DATA
-- ========================================

-- Insert default tier configurations
INSERT INTO tier_config (tier, hourly_limit, monthly_limit, cost_per_1k_tokens, max_expiry_days) VALUES
    ('free', 20, 500, 0.010, 180),
    ('pro', 100, 2000, 0.007, 180),
    ('enterprise', 2000, NULL, 0.005, 180)
ON CONFLICT (tier) DO NOTHING;

-- Create default admin user
INSERT INTO users (email, password_hash, name, is_admin, is_active, auth_provider, email_verified)
SELECT 'admin@devforge.ai', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3bp.Gm.F5e', 'Admin User', true, true, 'local', true
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@devforge.ai');

-- ========================================
-- VERIFICATION
-- ========================================

-- Update statistics
ANALYZE;

-- Final verification
DO $$
BEGIN
    RAISE NOTICE '=== DevForge Initial Schema Creation Complete ===';
    RAISE NOTICE 'Core tables created: users, tier_config, api_keys, request_logs, llm_usage, monthly_usage';
    RAISE NOTICE 'Enhancement tables created: tenant_config, rate_limit_cache, audit_log, user_sessions';
    RAISE NOTICE 'RAG vectors table: %', 
        CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rag_vectors') 
        THEN 'Created/Preserved' 
        ELSE 'Missing - requires pgvector extension' END;
    RAISE NOTICE 'Indexes created for performance optimization';
    RAISE NOTICE 'Views created for common queries';
    RAISE NOTICE 'Stored procedures created for common operations';
    RAISE NOTICE 'Database roles created: app_user, app_admin, app_readonly';
    RAISE NOTICE 'Default tier configurations inserted';
    RAISE NOTICE 'Default admin user created: admin@devforge.ai';
    RAISE NOTICE 'Schema creation completed successfully on %', now();
END $$;
