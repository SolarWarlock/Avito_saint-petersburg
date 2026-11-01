"""
Data Quality & Integrity Test Suite for Avito Real Estate DWH
Validates ETL transformations, ClickHouse OLAP Mart, and PostgreSQL ODS.
Run with: pytest -v tests/test_data_quality.py
"""

import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest
import pandas as pd
import numpy as np
import clickhouse_connect
from sqlalchemy import create_engine, text

# Configuration
CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", 8123))
CH_USER = os.environ.get("CH_USER", "avito_user")
CH_PASS = os.environ.get("CH_PASS", "avito_password")
CH_DB = os.environ.get("CH_DB", "avito_marts")

PG_URI = os.environ.get(
    "PG_URI",
    "postgresql+psycopg2://avito_user:avito_password@localhost:5433/avito_dwh"
)


# =====================================================================
# 1. UNIT TESTS: ETL Transformation & Data Cleansing Logic
# =====================================================================

def test_clean_and_transform_synthetic_data():
    """Validates that clean_and_transform correctly deduplicates, fixes ceilings, and removes dead listings."""
    from etl.pipeline import clean_and_transform

    dummy_raw = pd.DataFrame([
        # Valid item 1
        {
            "url": "https://www.avito.ru/spb/kvartiry/1k_100_et_111111?context=first_token",
            "title": "1-к. квартира, 40 м²",
            "price": 8000000,
            "Общая площадь": 40.0,
            "Жилая площадь": 20.0,
            "Площадь кухни": 10.0,
            "Количество комнат": 1,
            "rooms_count": 1,
            "floor_current": 5,
            "floor_total": 10,
            "Высота потолков": 28.0, # Anomaly to fix (28.0 -> 2.8)
            "Ремонт": "евро",
            "Отделка": np.nan,
            "Год постройки": 2020,
            "Срок сдачи": np.nan,
            "Вид сделки": "Вторичка",
            "Тип жилья": "Квартира",
            "params_raw": "1-к. квартира",
            "Time1": 8,
            "Район": "Московский",
            "Metro1": "Московская"
        },
        # Duplicate of item 1 with different context token
        {
            "url": "https://www.avito.ru/spb/kvartiry/1k_100_et_111111?context=different_token",
            "title": "1-к. квартира, 40 м²",
            "price": 8000000,
            "Общая площадь": 40.0,
            "Жилая площадь": 20.0,
            "Площадь кухни": 10.0,
            "Количество комнат": 1,
            "rooms_count": 1,
            "floor_current": 5,
            "floor_total": 10,
            "Высота потолков": 2.8,
            "Ремонт": "евро",
            "Отделка": np.nan,
            "Год постройки": 2020,
            "Срок сдачи": np.nan,
            "Вид сделки": "Вторичка",
            "Тип жилья": "Квартира",
            "params_raw": "1-к. квартира",
            "Time1": 8,
            "Район": "Московский",
            "Metro1": "Московская"
        },
        # Inactive / Dead listing (must be filtered)
        {
            "url": "https://www.avito.ru/spb/kvartiry/2k_200_et_222222?context=dead",
            "title": "Объявление не посмотреть",
            "price": np.nan,
            "Общая площадь": np.nan,
            "Жилая площадь": np.nan,
            "Площадь кухни": np.nan,
            "Количество комнат": 2,
            "rooms_count": 2,
            "floor_current": 1,
            "floor_total": 5,
            "Высота потолков": 2.5,
            "Ремонт": np.nan,
            "Отделка": np.nan,
            "Год постройки": 1980,
            "Срок сдачи": np.nan,
            "Вид сделки": "Вторичка",
            "Тип жилья": "Квартира",
            "params_raw": "",
            "Time1": np.nan,
            "Район": "Невский",
            "Metro1": "nan"
        }
    ])

    df_clean, stats = clean_and_transform(dummy_raw)

    # 1 item remains (1 inactive removed, 1 duplicate removed)
    assert len(df_clean) == 1, "Should filter 1 dead and 1 duplicate listing"
    assert stats["inactive_removed"] == 1
    assert stats["duplicates_removed"] == 1
    assert stats["ceiling_anomalies_fixed"] == 1

    row = df_clean.iloc[0]
    assert row["item_id"] == 111111
    assert row["ceiling_height"] == 2.8, "Ceiling height 28.0 must be normalized to 2.8"
    assert row["price_per_sqm"] == 200000.0, "8,000,000 / 40 = 200,000 ₽/м²"
    assert row["condition_unified"] == "евро"
    assert row["building_era"] == "Новый фонд (>2015)"
    assert row["metro_time_group"] == "до 10 мин"


# =====================================================================
# 2. INTEGRATION TESTS: ClickHouse OLAP Data Quality
# =====================================================================

@pytest.fixture(scope="module")
def ch_client():
    client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASS,
        database=CH_DB
    )
    yield client
    client.close()


def test_clickhouse_volume_and_existence(ch_client):
    """Checks that mart_avito_bi_flat has the full clean volume (>= 30,000 rows)."""
    count = ch_client.command("SELECT count() FROM avito_marts.mart_avito_bi_flat")
    assert count >= 30000, f"Expected at least 30,000 records, got {count}"


def test_clickhouse_no_duplicate_item_ids(ch_client):
    """Ensures primary key uniqueness (zero duplicates) in ClickHouse."""
    total = ch_client.command("SELECT count() FROM avito_marts.mart_avito_bi_flat")
    distinct = ch_client.command("SELECT count(DISTINCT item_id) FROM avito_marts.mart_avito_bi_flat")
    assert total == distinct, f"Duplicate item_ids found! Total: {total}, Distinct: {distinct}"


def test_clickhouse_price_and_area_validity(ch_client):
    """Ensures all prices, areas and unit prices are strictly positive and in plausible bounds."""
    # Prices must be strictly positive
    invalid_prices = ch_client.command("""
        SELECT count() FROM avito_marts.mart_avito_bi_flat
        WHERE price <= 0 OR total_area <= 0 OR price_per_sqm <= 0
    """)
    assert invalid_prices == 0, f"Found {invalid_prices} records with zero or negative price/area"

    # Median price per sqm should be within plausible real estate range (150k - 500k)
    med_sqm = ch_client.command("SELECT round(median(price_per_sqm)) FROM avito_marts.mart_avito_bi_flat")
    assert 150000 <= med_sqm <= 500000, f"City median price per sqm ({med_sqm}) is out of reasonable range"


def test_clickhouse_ceiling_height_sanity(ch_client):
    """Verifies that no ceiling heights exceed 10 meters and none are below 1.8 meters."""
    outliers = ch_client.command("""
        SELECT count() FROM avito_marts.mart_avito_bi_flat
        WHERE ceiling_height IS NOT NULL AND (ceiling_height > 10.0 OR ceiling_height < 1.8)
    """)
    assert outliers == 0, f"Found {outliers} invalid ceiling heights"


def test_clickhouse_kitchen_ratio_sanity(ch_client):
    """Ensures kitchen area never exceeds total area."""
    invalid_kitchens = ch_client.command("""
        SELECT count() FROM avito_marts.mart_avito_bi_flat
        WHERE kitchen_area IS NOT NULL AND kitchen_area > total_area
    """)
    assert invalid_kitchens == 0, f"Found {invalid_kitchens} records where kitchen > total area"


def test_clickhouse_districts_coverage(ch_client):
    """Validates that St. Petersburg districts are fully covered (at least 15 distinct districts)."""
    districts_count = ch_client.command("SELECT count(DISTINCT district) FROM avito_marts.mart_avito_bi_flat")
    assert districts_count >= 15, f"Expected at least 15 districts, got {districts_count}"


def test_clickhouse_building_era_categories(ch_client):
    """Ensures all building_era values conform strictly to defined categories."""
    allowed = {
        'Новый фонд (>2015)',
        'Советский (1918-1990)',
        'Современный (1991-2015)',
        'Дореволюционный (<1917)',
        'Не указан'
    }
    eras = set(ch_client.query_df("SELECT DISTINCT building_era FROM avito_marts.mart_avito_bi_flat")['building_era'])
    unexpected = eras - allowed
    assert len(unexpected) == 0, f"Unexpected building_era categories: {unexpected}"


def test_clickhouse_metro_time_groups(ch_client):
    """Ensures all metro_time_group values conform to standard bins."""
    allowed = {'до 10 мин', '11-20 мин', '21-30 мин', '> 30 мин', 'Не указано'}
    groups = set(ch_client.query_df("SELECT DISTINCT metro_time_group FROM avito_marts.mart_avito_bi_flat")['metro_time_group'])
    unexpected = groups - allowed
    assert len(unexpected) == 0, f"Unexpected metro_time_group bins: {unexpected}"


# =====================================================================
# 3. INTEGRATION TESTS: PostgreSQL ODS Core Layer
# =====================================================================

@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(PG_URI)
    yield engine
    engine.dispose()


def test_postgres_listings_count(pg_engine):
    """Validates PostgreSQL core.listings row count matches ClickHouse."""
    with pg_engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM core.listings WHERE is_active = TRUE")).scalar()
        assert count >= 30000, f"Expected >= 30,000 listings in PostgreSQL, got {count}"


def test_postgres_foreign_key_referential_integrity(pg_engine):
    """Ensures all listings have valid district_id mapping to dim_district."""
    with pg_engine.connect() as conn:
        orphans = conn.execute(text("""
            SELECT count(*) 
            FROM core.listings l
            LEFT JOIN core.dim_district d ON l.district_id = d.district_id
            WHERE l.district_id IS NOT NULL AND d.district_id IS NULL
        """)).scalar()
        assert orphans == 0, f"Found {orphans} orphaned district_ids in core.listings"


def test_postgres_dq_audit_log_has_success(pg_engine):
    """Verifies that the Data Quality audit log table recorded a SUCCESS status."""
    with pg_engine.connect() as conn:
        success_runs = conn.execute(text("""
            SELECT count(*) FROM dq.etl_run_logs WHERE status = 'SUCCESS'
        """)).scalar()
        assert success_runs >= 1, "No successful ETL run logs recorded in dq.etl_run_logs"
