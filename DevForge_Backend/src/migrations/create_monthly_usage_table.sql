-- Create monthly_usage table for persistent rate limit tracking
-- This table survives Redis restarts and provides monthly usage persistence

CREATE TABLE IF NOT EXISTS monthly_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID REFERENCES api_keys(id) 
        ON DELETE CASCADE,
    year_month TEXT NOT NULL,  -- "2026-03" format
    tokens_used INTEGER DEFAULT 0,
    requests_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE 
        DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(api_key_id, year_month)
);

-- Create index for efficient lookups
CREATE INDEX IF NOT EXISTS monthly_usage_key_month 
ON monthly_usage(api_key_id, year_month);

-- Create index for cleanup queries
CREATE INDEX IF NOT EXISTS monthly_usage_last_updated 
ON monthly_usage(last_updated);
