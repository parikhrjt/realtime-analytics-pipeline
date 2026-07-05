-- Initial schema for realtime analytics pipeline

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS raw_events (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    event_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_events_type_ts ON raw_events (event_type, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_events_user_ts ON raw_events (user_id, event_timestamp);

CREATE TABLE IF NOT EXISTS user_signups (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(100) NOT NULL,
    signup_source VARCHAR(50) NOT NULL DEFAULT 'organic',
    country CHAR(2) NOT NULL DEFAULT 'US',
    event_timestamp TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_signups_ts ON user_signups (event_timestamp);

CREATE TABLE IF NOT EXISTS page_views (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(100) NOT NULL,
    page_path VARCHAR(255) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    referrer VARCHAR(100),
    event_timestamp TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_page_views_ts ON page_views (event_timestamp);
CREATE INDEX IF NOT EXISTS idx_page_views_user_ts ON page_views (user_id, event_timestamp);

CREATE TABLE IF NOT EXISTS purchases (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(100) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    product_id VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_purchases_ts ON purchases (event_timestamp);

CREATE TABLE IF NOT EXISTS subscription_cancellations (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(100) NOT NULL,
    plan_tier VARCHAR(50) NOT NULL,
    reason VARCHAR(100) NOT NULL DEFAULT 'unknown',
    months_subscribed INT,
    event_timestamp TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subscription_cancellations_ts
    ON subscription_cancellations (event_timestamp);

CREATE TABLE IF NOT EXISTS referrals (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(100) NOT NULL,
    referrer_id VARCHAR(100) NOT NULL,
    referred_user_id VARCHAR(100) NOT NULL,
    campaign VARCHAR(100),
    event_timestamp TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_referrals_ts ON referrals (event_timestamp);

CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id BIGSERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value NUMERIC(18, 6) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (metric_date, metric_name)
);

CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_name_date
    ON kpi_snapshots (metric_name, metric_date DESC);

CREATE TABLE IF NOT EXISTS anomalies (
    id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(50) NOT NULL,
    metric_date DATE NOT NULL,
    current_value NUMERIC(18, 6),
    expected_value NUMERIC(18, 6),
    deviation_pct NUMERIC(8, 4),
    severity VARCHAR(20) NOT NULL DEFAULT 'warning',
    message TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomalies_detected_at ON anomalies (detected_at DESC);
