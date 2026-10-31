-- ========================================================
-- Schema Initialization for Avito Real Estate DWH (PostgreSQL)
-- Database: avito_dwh
-- ========================================================

CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS dq;

-- --------------------------------------------------------
-- 1. STAGING LAYER: Raw scraped records
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.avito_listings_raw (
    raw_id SERIAL PRIMARY KEY,
    url TEXT,
    title TEXT,
    price NUMERIC,
    address TEXT,
    params_raw TEXT,
    description TEXT,
    district TEXT,
    clean_address TEXT,
    metro1 TEXT,
    metro2 TEXT,
    metro3 TEXT,
    time1 NUMERIC,
    time2 NUMERIC,
    time3 NUMERIC,
    city TEXT,
    rooms_count_raw TEXT,
    total_area NUMERIC,
    kitchen_area NUMERIC,
    living_area NUMERIC,
    floor_raw TEXT,
    apartment_type TEXT,
    deal_type TEXT,
    year_built NUMERIC,
    ceiling_height NUMERIC,
    renovation TEXT,
    finishing TEXT,
    deadline TEXT,
    renovation_cost NUMERIC,
    floor_current NUMERIC,
    floor_total NUMERIC,
    rooms_count NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- --------------------------------------------------------
-- 2. CORE LAYER: Normalized Dimensions & Fact Table
-- --------------------------------------------------------

-- Dimension: Districts of St. Petersburg
CREATE TABLE IF NOT EXISTS core.dim_district (
    district_id SERIAL PRIMARY KEY,
    district_name VARCHAR(100) UNIQUE NOT NULL,
    macro_zone VARCHAR(50) -- e.g., 'Юг', 'Восток', 'Юго-Запад'
);

-- Dimension: Metro Stations
CREATE TABLE IF NOT EXISTS core.dim_metro (
    metro_id SERIAL PRIMARY KEY,
    metro_name VARCHAR(100) UNIQUE NOT NULL,
    metro_line VARCHAR(50)
);

-- Fact: Cleaned & Normalized Listings
CREATE TABLE IF NOT EXISTS core.listings (
    item_id BIGINT PRIMARY KEY,
    url TEXT NOT NULL,
    title VARCHAR(255),
    price NUMERIC(14, 2) NOT NULL,
    price_per_sqm NUMERIC(10, 2) NOT NULL,
    total_area NUMERIC(6, 2) NOT NULL,
    living_area NUMERIC(6, 2),
    kitchen_area NUMERIC(6, 2),
    rooms_count INT,
    floor_current INT,
    floor_total INT,
    is_first_floor BOOLEAN,
    is_last_floor BOOLEAN,
    ceiling_height NUMERIC(4, 2),
    year_built_unified INT,
    condition_unified VARCHAR(100),
    renovation_cost NUMERIC(12, 2),
    object_type VARCHAR(50) NOT NULL, -- 'Квартира', 'Апартаменты', 'Доля'
    market_type VARCHAR(50) NOT NULL, -- 'Вторичка', 'Новостройка'
    district_id INT REFERENCES core.dim_district(district_id),
    metro_primary_id INT REFERENCES core.dim_metro(metro_id),
    time_to_metro_min INT,
    address TEXT,
    clean_address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for analytical query acceleration in PostgreSQL
CREATE INDEX IF NOT EXISTS idx_listings_district ON core.listings(district_id);
CREATE INDEX IF NOT EXISTS idx_listings_price_per_sqm ON core.listings(price_per_sqm);
CREATE INDEX IF NOT EXISTS idx_listings_market_type ON core.listings(market_type);
CREATE INDEX IF NOT EXISTS idx_listings_object_type ON core.listings(object_type);

-- --------------------------------------------------------
-- 3. DATA QUALITY LAYER: ETL Audit & Validation Logs
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.etl_run_logs (
    run_id SERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_file VARCHAR(255),
    total_raw_rows INT,
    valid_rows_inserted INT,
    duplicates_filtered INT,
    inactive_filtered INT,
    ceiling_anomalies_fixed INT,
    status VARCHAR(50),
    error_message TEXT
);

