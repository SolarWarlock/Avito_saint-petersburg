CREATE DATABASE IF NOT EXISTS avito_marts;

-- ========================================================
-- Analytical Flat Mart for Superset BI Dashboards
-- ========================================================
CREATE TABLE IF NOT EXISTS avito_marts.mart_avito_bi_flat
(
    item_id UInt64,
    url String,
    title String,
    price Float64,
    price_per_sqm Float64,
    total_area Float32,
    living_area Nullable(Float32),
    kitchen_area Nullable(Float32),
    kitchen_to_total_ratio Nullable(Float32),
    rooms_count Nullable(Int16),
    floor_current Nullable(Int16),
    floor_total Nullable(Int16),
    floor_category LowCardinality(String), -- 'Первый', 'Последний', 'Средний'
    ceiling_height Nullable(Float32),
    year_built_unified Nullable(Int16),
    building_era LowCardinality(String),   -- 'Дореволюционный (<1917)', 'Советский (1918-1990)', 'Современный (1991-2015)', 'Новый фонд (>2015)'
    condition_unified LowCardinality(String),
    renovation_cost Nullable(Float64),
    renovation_to_price_ratio Nullable(Float32),
    object_type LowCardinality(String),    -- 'Квартира', 'Апартаменты', 'Доля'
    market_type LowCardinality(String),    -- 'Вторичка', 'Новостройка'
    district LowCardinality(String),
    metro1 LowCardinality(String),
    time1 Nullable(Float32),
    metro_time_group LowCardinality(String), -- 'до 10 мин', '11-20 мин', '21-30 мин', '> 30 мин'
    address String,
    clean_address String,
    loaded_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
ORDER BY (district, item_id);

-- ========================================================
-- Direct Federated Link to PostgreSQL ODS (Avito DWH)
-- ========================================================
CREATE DATABASE IF NOT EXISTS pg_dwh
ENGINE = PostgreSQL('postgres:5432', 'avito_dwh', 'avito_user', 'avito_password');
