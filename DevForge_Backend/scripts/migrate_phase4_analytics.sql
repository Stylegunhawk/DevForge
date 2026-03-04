-- Phase 4 Analytics Migration Script
-- Adds user_id tracking and request logging capabilities

-- 1. Add user_id to existing llm_usage table
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;

-- 2. Create index for performance on llm_usage.user_id
CREATE INDEX IF NOT EXISTS llm_usage_user_idx ON llm_usage(user_id);

-- 3. Create new request_logs table for tool-level observability
CREATE TABLE IF NOT EXISTS request_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id TEXT,
    integration_name TEXT,
    tool_name TEXT NOT NULL,
    input_summary TEXT, -- Truncated to 500 chars
    success BOOLEAN DEFAULT true,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Performance indices for request_logs
CREATE INDEX IF NOT EXISTS request_logs_user_idx ON request_logs(user_id);
CREATE INDEX IF NOT EXISTS request_logs_tool_idx ON request_logs(tool_name);
CREATE INDEX IF NOT EXISTS request_logs_created_at_idx ON request_logs(created_at);
CREATE INDEX IF NOT EXISTS request_logs_tenant_idx ON request_logs(tenant_id);

-- 5. Composite index for common dashboard queries
CREATE INDEX IF NOT EXISTS request_logs_dashboard_idx ON request_logs(created_at, tool_name, success);

-- 6. Optimized index for user-specific date range queries
CREATE INDEX IF NOT EXISTS request_logs_user_created_idx ON request_logs(user_id, created_at DESC);

COMMIT;
