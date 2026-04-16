-- Active: 1776382401625@@aws-0-eu-west-1.pooler.supabase.com@6543@postgres
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    price_min NUMERIC(10,2),
    price_max NUMERIC(10,2),
    rating NUMERIC(3,2),
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_scraped
    ON price_history(product_id, scraped_at DESC);
