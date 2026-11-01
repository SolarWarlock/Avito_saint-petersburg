-- =====================================================================
-- 📊 АВИТО НЕДВИЖИМОСТЬ: ПРИКЛАДНЫЕ ПРОДУКТОВЫЕ SQL-ЗАПРОСЫ
-- Аналитический стек: ClickHouse (OLAP Mart) & PostgreSQL 15 (ODS / Core DWH)
-- Проект: Мониторинг рынка жилой недвижимости Санкт-Петербурга (31k+ объявлений)
-- =====================================================================

-- ---------------------------------------------------------------------
-- КЕЙС 1 (ClickHouse). Инвестиционный скоринг и поиск недооцененных лотов
-- Бизнес-цель: Алгоритм для витрины инвесторов / флипперов. Поиск квартир,
-- чья цена за м² более чем на 25% ниже локальной медианы микрорайона
-- (комбинация: Район + Метро + Комнатность). Исключаются аукционы и доли.
-- ---------------------------------------------------------------------
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
    HAVING count() >= 10 -- Репрезентативный кластер
),
ranked_deals AS (
    SELECT
        f.item_id,
        f.title,
        f.district,
        f.metro1,
        f.rooms_count,
        f.price,
        round(f.price_per_sqm)                  AS price_per_sqm,
        round(c.cluster_median_sqm)             AS cluster_median_sqm,
        round((1 - f.price_per_sqm / c.cluster_median_sqm) * 100, 1) AS discount_pct,
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
      AND f.price_per_sqm < c.cluster_median_sqm * 0.75 -- Скидка от 25%
)
SELECT 
    item_id,
    title,
    district,
    metro1,
    rooms_count,
    price,
    price_per_sqm,
    cluster_median_sqm,
    discount_pct,
    deal_rank
FROM ranked_deals
WHERE deal_rank <= 3 -- Топ-3 недооцененных лота по каждому району
ORDER BY district, discount_pct DESC;


-- ---------------------------------------------------------------------
-- КЕЙС 2 (ClickHouse). Оценка дисконта за первый и последний этажи
-- Бизнес-цель: Определение эластичности цены по вертикали здания. 
-- Насколько рынок штрафует первый этаж и какую премию/дисконт дает
-- последний (видовой) этаж относительно типового среднего?
-- ---------------------------------------------------------------------
SELECT
    district,
    count()                                                         AS total_listings,
    round(medianIf(price_per_sqm, floor_category = 'Первый'))       AS first_floor_med_sqm,
    round(medianIf(price_per_sqm, floor_category = 'Средний'))      AS mid_floor_med_sqm,
    round(medianIf(price_per_sqm, floor_category = 'Последний'))    AS last_floor_med_sqm,
    -- Процентный дисконт первого этажа к среднему
    round((1 - medianIf(price_per_sqm, floor_category = 'Первый') / 
               medianIf(price_per_sqm, floor_category = 'Средний')) * 100, 1) AS first_floor_discount_pct,
    -- Процентный дисконт/премия последнего этажа к среднему (минус означает премию)
    round((1 - medianIf(price_per_sqm, floor_category = 'Последний') / 
               medianIf(price_per_sqm, floor_category = 'Средний')) * 100, 1) AS last_floor_discount_pct
FROM avito_marts.mart_avito_bi_flat
WHERE object_type = 'Квартира'
GROUP BY district
HAVING count() >= 500
ORDER BY mid_floor_med_sqm DESC;


-- ---------------------------------------------------------------------
-- КЕЙС 3 (ClickHouse). Экономика ремонта: Арбитраж и окупаемость отделки
-- Бизнес-цель: Расчет добавочной рыночной стоимости каждого типа ремонта
-- по отношению к объектам «Без ремонта / Черновая» в разрезе эпох постройки.
-- Позволяет инвесторам оценить ROI ремонтных работ на типовые 50 м².
-- ---------------------------------------------------------------------
WITH base_costs AS (
    SELECT
        building_era,
        condition_unified,
        count()                             AS lot_count,
        round(median(price_per_sqm))        AS med_sqm
    FROM avito_marts.mart_avito_bi_flat
    WHERE object_type = 'Квартира'
    GROUP BY building_era, condition_unified
    HAVING count() >= 20
),
rough_benchmark AS (
    -- Базовый бенчмарк без отделки для каждого периода постройки
    SELECT
        building_era,
        med_sqm                             AS rough_med_sqm
    FROM base_costs
    WHERE condition_unified IN ('без отделки', 'Без ремонта / Черновая', 'требует ремонта')
    QUALIFY row_number() OVER (PARTITION BY building_era ORDER BY lot_count DESC) = 1
)
SELECT
    b.building_era,
    b.condition_unified,
    b.lot_count,
    b.med_sqm                               AS current_med_sqm,
    r.rough_med_sqm                         AS benchmark_rough_sqm,
    (b.med_sqm - r.rough_med_sqm)           AS renovation_premium_per_sqm,
    -- Расчет добавленной стоимости объекта площадью 50 кв. м (в млн рублей)
    round((b.med_sqm - r.rough_med_sqm) * 50 / 1000000, 2) AS est_added_value_50sqm_mln
FROM base_costs b
JOIN rough_benchmark r ON b.building_era = r.building_era
WHERE b.condition_unified NOT IN ('без отделки', 'Без ремонта / Черновая', 'требует ремонта')
ORDER BY b.building_era, renovation_premium_per_sqm DESC;


-- ---------------------------------------------------------------------
-- КЕЙС 4 (ClickHouse). Транспортный градиент: цена шага удаления от метро
-- Бизнес-цель: Расчет эластичности стоимости кв. метра в зависимости от
-- времени пешком до метро с использованием оконной функции LAG.
-- Сколько тысяч рублей теряет метр при переходе в более далекую категорию?
-- ---------------------------------------------------------------------
WITH metro_times AS (
    SELECT
        district,
        metro_time_group,
        count()                                                 AS n_listings,
        round(median(price_per_sqm))                            AS med_sqm,
        CASE metro_time_group
            WHEN 'до 10 мин'  THEN 1
            WHEN '11-20 мин'  THEN 2
            WHEN '21-30 мин'  THEN 3
            WHEN '> 30 мин'   THEN 4
            ELSE 5
        END                                                     AS time_order
    FROM avito_marts.mart_avito_bi_flat
    WHERE object_type = 'Квартира' 
      AND metro_time_group != 'Не указано'
    GROUP BY district, metro_time_group
    HAVING count() >= 30
),
gradient AS (
    SELECT
        district,
        metro_time_group,
        time_order,
        n_listings,
        med_sqm,
        -- Берем медиану предыдущей (более близкой к метро) группы
        lagInFrame(med_sqm, 1) OVER (PARTITION BY district ORDER BY time_order) AS prev_closer_med_sqm
    FROM metro_times
)
SELECT
    district,
    metro_time_group,
    n_listings,
    med_sqm,
    prev_closer_med_sqm,
    -- Абсолютная разница в цене за м² при удалении от метро
    if(prev_closer_med_sqm IS NULL, 0, prev_closer_med_sqm - med_sqm) AS drop_per_sqm_rub,
    -- Относительное падение в процентах
    round(if(prev_closer_med_sqm IS NULL, 0, (1 - med_sqm / prev_closer_med_sqm) * 100), 1) AS drop_pct
FROM gradient
WHERE district IN ('Приморский', 'Московский', 'Невский', 'Калининский', 'Центральный')
ORDER BY district, time_order;


-- ---------------------------------------------------------------------
-- КЕЙС 5 (ClickHouse). Матрица доступности жилья и ипотечное моделирование
-- Бизнес-цель: Построение перцентильного распределения цен (P25, P50, P75)
-- по комнатности с расчетом требуемого ежемесячного дохода семьи
-- при стандартной ставке 18%, сроке 25 лет и первоначальном взносе 20% (ПДН 50%).
-- ---------------------------------------------------------------------
WITH room_stats AS (
    SELECT
        rooms_count,
        count()                                                         AS count_offers,
        round(count() * 100.0 / sum(count()) OVER (), 1)               AS market_share_pct,
        round(quantilesExact(0.25, 0.50, 0.75)(price)[1])               AS p25_price_rub,
        round(quantilesExact(0.25, 0.50, 0.75)(price)[2])               AS p50_price_rub,
        round(quantilesExact(0.25, 0.50, 0.75)(price)[3])               AS p75_price_rub,
        round(quantilesExact(0.25, 0.50, 0.75)(price_per_sqm)[2])       AS p50_sqm_rub,
        round(median(total_area), 1)                                    AS p50_area_sqm
    FROM avito_marts.mart_avito_bi_flat
    WHERE object_type = 'Квартира' AND rooms_count <= 4
    GROUP BY rooms_count
)
SELECT
    CASE rooms_count
        WHEN 0 THEN 'Студия'
        WHEN 1 THEN '1-комнатная'
        WHEN 2 THEN '2-комнатная'
        WHEN 3 THEN '3-комнатная'
        WHEN 4 THEN '4+-комнатная'
    END                                                                 AS room_type,
    count_offers,
    market_share_pct,
    p50_area_sqm,
    p50_sqm_rub,
    -- Бюджет покупки в млн ₽
    round(p25_price_rub / 1000000, 2)                                  AS p25_budget_mln,
    round(p50_price_rub / 1000000, 2)                                  AS p50_median_budget_mln,
    round(p75_price_rub / 1000000, 2)                                  AS p75_budget_mln,
    -- Ипотечный расчет: кредит 80%, аннуитетный коэффициент на 25 лет под 18% годовых (~0.01515)
    round((p50_price_rub * 0.8) * 0.01515)                             AS est_monthly_payment_rub,
    -- Рекомендуемый доход семьи (при условии, что платёж не более 50% дохода)
    round((p50_price_rub * 0.8 * 0.01515) * 2)                         AS req_monthly_income_rub
FROM room_stats
ORDER BY rooms_count;


-- ---------------------------------------------------------------------
-- КЕЙС 6 (PostgreSQL). Анализ качества данных и мониторинг целостности ODS
-- Бизнес-цель: Аудит качества загрузки в ядро DWH: проверка связности
-- измерений dim_district, dim_metro, а также поиск скрытых выбросов.
-- ---------------------------------------------------------------------
SELECT
    d.district_name,
    count(l.item_id)                                                    AS total_active_listings,
    count(CASE WHEN l.price_per_sqm < 80000 THEN 1 END)                 AS suspiciously_cheap_lots,
    count(CASE WHEN l.price_per_sqm > 1000000 THEN 1 END)               AS ultra_luxury_lots,
    count(CASE WHEN l.kitchen_area >= l.total_area THEN 1 END)          AS invalid_kitchen_ratio_count,
    count(CASE WHEN l.metro_primary_id IS NULL THEN 1 END)              AS unmapped_metro_count,
    round(avg(l.price_per_sqm))                                         AS avg_price_per_sqm,
    round(stddev(l.price_per_sqm))                                      AS stddev_price_per_sqm
FROM core.listings l
LEFT JOIN core.dim_district d ON l.district_id = d.district_id
WHERE l.is_active = TRUE
GROUP BY d.district_name
ORDER BY total_active_listings DESC;
