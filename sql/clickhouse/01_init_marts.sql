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

-- ========================================================
-- Product Analytical View 1: Underpriced Deals (Flips & Bargains)
-- ========================================================
CREATE OR REPLACE VIEW avito_marts.mart_underpriced_deals AS
WITH cluster_stats AS (
    SELECT
        district,
        metro1,
        rooms_count,
        count()                                 AS cluster_listings,
        median(price_per_sqm)                   AS cluster_median_sqm
    FROM avito_marts.mart_avito_bi_flat
    WHERE object_type = 'Квартира'
      AND metro1 != 'Без метро'
      AND title NOT ILIKE '%аукцион%'
      AND title NOT ILIKE '%доля%'
    GROUP BY district, metro1, rooms_count
    HAVING count() >= 8
),
ranked_deals AS (
    SELECT
        f.item_id,
        f.title,
        f.district,
        f.metro1,
        f.rooms_count,
        f.total_area,
        f.floor_current,
        f.floor_total,
        f.condition_unified,
        f.building_era,
        f.price,
        round(f.price_per_sqm)                  AS price_per_sqm,
        round(c.cluster_median_sqm)             AS cluster_median_sqm,
        round((1 - f.price_per_sqm / c.cluster_median_sqm) * 100, 1) AS discount_pct,
        round((1 - f.price_per_sqm / c.cluster_median_sqm), 4)       AS discount_ratio,
        round((c.cluster_median_sqm - f.price_per_sqm) * f.total_area) AS potential_gain_rub,
        row_number() OVER (
            PARTITION BY f.district 
            ORDER BY (c.cluster_median_sqm - f.price_per_sqm) DESC
        ) AS deal_rank
    FROM avito_marts.mart_avito_bi_flat f
    JOIN cluster_stats c 
      ON f.district = c.district 
     AND f.metro1 = c.metro1 
     AND f.rooms_count = c.rooms_count
    WHERE f.object_type = 'Квартира'
      AND f.title NOT ILIKE '%аукцион%'
      AND f.title NOT ILIKE '%доля%'
      AND f.price_per_sqm < c.cluster_median_sqm * 0.75
)
SELECT 
    item_id,
    title,
    district,
    metro1,
    rooms_count,
    total_area,
    floor_current,
    floor_total,
    condition_unified,
    building_era,
    price,
    price_per_sqm,
    cluster_median_sqm,
    discount_pct,
    discount_ratio,
    potential_gain_rub,
    deal_rank
FROM ranked_deals
WHERE deal_rank <= 5;

-- ========================================================
-- Product Analytical View 2: Floor Penalty Matrix
-- ========================================================
CREATE OR REPLACE VIEW avito_marts.mart_floor_penalty_matrix AS
SELECT
    district,
    count()                                                         AS listings_count,
    round(medianIf(price_per_sqm, floor_category = 'Первый'))       AS first_floor_med_sqm,
    round(medianIf(price_per_sqm, floor_category = 'Средний'))      AS mid_floor_med_sqm,
    round(medianIf(price_per_sqm, floor_category = 'Последний'))    AS last_floor_med_sqm,
    round((1 - medianIf(price_per_sqm, floor_category = 'Первый') / 
               nullif(medianIf(price_per_sqm, floor_category = 'Средний'), 0)) * 100, 1) AS first_floor_discount_pct,
    round((1 - medianIf(price_per_sqm, floor_category = 'Последний') / 
               nullif(medianIf(price_per_sqm, floor_category = 'Средний'), 0)) * 100, 1) AS last_floor_discount_pct
FROM avito_marts.mart_avito_bi_flat
WHERE object_type = 'Квартира'
GROUP BY district
HAVING count() >= 300;

