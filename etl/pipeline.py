"""
ETL Pipeline & Data Quality for Avito St. Petersburg Real Estate
Target architectures: PostgreSQL 15 (ODS/Core) + ClickHouse (OLAP Mart)
"""

import os
import re
import sys
import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import clickhouse_connect

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("avito_etl")

# Configurable Connection Strings
PG_URI = os.environ.get(
    "PG_URI",
    "postgresql+psycopg2://avito_user:avito_password@localhost:5433/avito_dwh"
)
CH_HOST = os.environ.get("CH_HOST", "localhost")
CH_PORT = int(os.environ.get("CH_PORT", 8123))
CH_USER = os.environ.get("CH_USER", "avito_user")
CH_PASS = os.environ.get("CH_PASS", "avito_password")
CH_DB = os.environ.get("CH_DB", "avito_marts")


def load_raw_data(filepath: str) -> pd.DataFrame:
    logger.info(f"Loading raw data from: {filepath}")
    if filepath.endswith('.xlsx') or filepath.endswith('.xls'):
        df = pd.read_excel(filepath)
    elif filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        raise ValueError(f"Unsupported file format: {filepath}")
    logger.info(f"Loaded raw dataset shape: {df.shape}")
    return df


def clean_and_transform(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats = {
        "raw_rows": len(df_raw),
        "inactive_removed": 0,
        "duplicates_removed": 0,
        "ceiling_anomalies_fixed": 0
    }
    
    df = df_raw.copy()
    
    # Remove empty/dead listings
    invalid_mask = (
        df['price'].isna() |
        df['Общая площадь'].isna() |
        (df['title'].str.contains("Объявление не посмотреть", na=False))
    )
    stats["inactive_removed"] = int(invalid_mask.sum())
    df = df[~invalid_mask].copy()
    logger.info(f"Filtered {stats['inactive_removed']} inactive/null listings. Remaining: {len(df)}")
    
    # Extract natural item_id from URL & Deduplicate
    # URLs look like: ..._kvartira_433_m_1319_et._7848678486?context=...
    extracted_ids = df['url'].str.extract(r'_(\d+)\?')
    df['item_id'] = extracted_ids[0].astype('int64')
    
    initial_len = len(df)
    df = df.drop_duplicates(subset=['item_id'], keep='first').copy()
    stats["duplicates_removed"] = initial_len - len(df)
    logger.info(f"Deduplicated by item_id: removed {stats['duplicates_removed']} duplicates. Remaining: {len(df)}")
    
    # 3. Clean numeric fields and fix anomalies
    df['price'] = df['price'].astype(float)
    df['total_area'] = df['Общая площадь'].astype(float)
    df['living_area'] = pd.to_numeric(df['Жилая площадь'], errors='coerce')
    df['kitchen_area'] = pd.to_numeric(df['Площадь кухни'], errors='coerce')
    df['rooms_count'] = pd.to_numeric(df['rooms_count'], errors='coerce').fillna(
        pd.to_numeric(df['Количество комнат'], errors='coerce')
    )
    df['floor_current'] = pd.to_numeric(df['floor_current'], errors='coerce')
    df['floor_total'] = pd.to_numeric(df['floor_total'], errors='coerce')
    
    # Ceiling height anomaly fix (e.g., 28.0 -> 2.8)
    df['ceiling_height'] = pd.to_numeric(df['Высота потолков'], errors='coerce')
    high_ceiling_mask = df['ceiling_height'] > 10.0
    stats["ceiling_anomalies_fixed"] = int(high_ceiling_mask.sum())
    df.loc[high_ceiling_mask, 'ceiling_height'] = df.loc[high_ceiling_mask, 'ceiling_height'] / 10.0
    df.loc[df['ceiling_height'] < 1.8, 'ceiling_height'] = np.nan
    logger.info(f"Fixed {stats['ceiling_anomalies_fixed']} ceiling height outliers")
    
    # Feature COALESCE condition (Ремонт vs Отделка)
    condition_unified = df['Ремонт'].fillna(df['Отделка']).fillna('Без ремонта / Черновая')
    df['condition_unified'] = condition_unified.astype(str)
    
    # Feature Unified Year Built
    year_built = pd.to_numeric(df['Год постройки'], errors='coerce')
    # If year_built is NaN, extract year from 'Срок сдачи' (e.g. "Сдача в 1 кв. 2028")
    deadline_year = df['Срок сдачи'].astype(str).str.extract(r'(\d{4})')[0]
    deadline_year_num = pd.to_numeric(deadline_year, errors='coerce')
    df['year_built_unified'] = year_built.fillna(deadline_year_num)
    
    # Building Era Category
    def classify_era(yr):
        if pd.isna(yr):
            return 'Не указан'
        yr = int(yr)
        if yr < 1917:
            return 'Дореволюционный (<1917)'
        elif yr <= 1990:
            return 'Советский (1918-1990)'
        elif yr <= 2015:
            return 'Современный (1991-2015)'
        else:
            return 'Новый фонд (>2015)'
            
    df['building_era'] = df['year_built_unified'].apply(classify_era)
    
    # Object Type: Квартира vs Апартаменты vs Доля
    def classify_object_type(row):
        title_lower = str(row['title']).lower()
        params_lower = str(row['params_raw']).lower()
        if 'доля' in title_lower or 'комната' in title_lower or 'доля' in params_lower:
            return 'Доля'
        elif 'апарт' in title_lower or 'апарт' in params_lower or str(row.get('Тип жилья', '')).lower() == 'апартаменты':
            return 'Апартаменты'
        return 'Квартира'
        
    df['object_type'] = df.apply(classify_object_type, axis=1)
    
    # Market Type: Вторичка vs Новостройка
    def classify_market_type(row):
        deal = str(row.get('Вид сделки', '')).lower()
        deadline = str(row.get('Срок сдачи', ''))
        if 'новострой' in deal or (deadline != 'nan' and len(deadline) > 3):
            return 'Новостройка'
        return 'Вторичка'
        
    df['market_type'] = df.apply(classify_market_type, axis=1)
    
    # Derived Metrics: Price per sqm & Ratios
    df['price_per_sqm'] = np.round(df['price'] / df['total_area'], 2)
    df['kitchen_to_total_ratio'] = np.round(df['kitchen_area'] / df['total_area'], 3)
    
    df['renovation_cost'] = pd.to_numeric(df.get('renovation_cost', np.nan), errors='coerce')
    df['renovation_to_price_ratio'] = np.round(df['renovation_cost'] / df['price'], 4)
    
    # Floor Category
    def classify_floor(row):
        cur = row['floor_current']
        tot = row['floor_total']
        if pd.isna(cur):
            return 'Не указан'
        if cur == 1:
            return 'Первый'
        elif not pd.isna(tot) and cur == tot:
            return 'Последний'
        return 'Средний'
        
    df['floor_category'] = df.apply(classify_floor, axis=1)
    
    # Metro time groups
    df['time1'] = pd.to_numeric(df.get('Time1', np.nan), errors='coerce')
    def classify_metro_time(t):
        if pd.isna(t):
            return 'Не указано'
        if t <= 10:
            return 'до 10 мин'
        elif t <= 20:
            return '11-20 мин'
        elif t <= 30:
            return '21-30 мин'
        return '> 30 мин'
        
    df['metro_time_group'] = df['time1'].apply(classify_metro_time)
    
    # Clean district & metro
    df['district'] = df['Район'].astype(str).str.strip().fillna('Не указан')
    df['metro1'] = df['Metro1'].astype(str).str.strip().replace({'nan': 'Без метро', '': 'Без метро'})
    
    logger.info(f"ETL Transformation complete. Final clean records: {len(df)}")
    return df, stats


def load_to_postgres(df: pd.DataFrame, stats: dict, pg_engine):
    logger.info("Starting PostgreSQL data load...")
    with pg_engine.begin() as conn:
        # 1. Populate dim_district
        districts = df['district'].unique()
        for dist in districts:
            conn.execute(
                text("""
                    INSERT INTO core.dim_district (district_name) 
                    VALUES (:name) 
                    ON CONFLICT (district_name) DO NOTHING
                """),
                {"name": dist}
            )
        
        # 2. Populate dim_metro
        metros = df['metro1'].unique()
        for metro in metros:
            conn.execute(
                text("""
                    INSERT INTO core.dim_metro (metro_name) 
                    VALUES (:name) 
                    ON CONFLICT (metro_name) DO NOTHING
                """),
                {"name": metro}
            )
            
        # Get mapping dictionaries
        dist_map = dict(conn.execute(text("SELECT district_name, district_id FROM core.dim_district")).fetchall())
        metro_map = dict(conn.execute(text("SELECT metro_name, metro_id FROM core.dim_metro")).fetchall())
        
        # 3. Populate fact table: core.listings
        conn.execute(text("TRUNCATE TABLE core.listings RESTART IDENTITY CASCADE;"))
        
        listings_records = []
        for _, row in df.iterrows():
            listings_records.append({
                "item_id": int(row['item_id']),
                "url": str(row['url']),
                "title": str(row['title'])[:250],
                "price": float(row['price']),
                "price_per_sqm": float(row['price_per_sqm']),
                "total_area": float(row['total_area']),
                "living_area": float(row['living_area']) if not pd.isna(row['living_area']) else None,
                "kitchen_area": float(row['kitchen_area']) if not pd.isna(row['kitchen_area']) else None,
                "rooms_count": int(row['rooms_count']) if not pd.isna(row['rooms_count']) else None,
                "floor_current": int(row['floor_current']) if not pd.isna(row['floor_current']) else None,
                "floor_total": int(row['floor_total']) if not pd.isna(row['floor_total']) else None,
                "is_first_floor": bool(row['floor_category'] == 'Первый'),
                "is_last_floor": bool(row['floor_category'] == 'Последний'),
                "ceiling_height": float(row['ceiling_height']) if not pd.isna(row['ceiling_height']) else None,
                "year_built_unified": int(row['year_built_unified']) if not pd.isna(row['year_built_unified']) else None,
                "condition_unified": str(row['condition_unified'])[:100],
                "renovation_cost": float(row['renovation_cost']) if not pd.isna(row['renovation_cost']) else None,
                "object_type": str(row['object_type']),
                "market_type": str(row['market_type']),
                "district_id": dist_map.get(row['district']),
                "metro_primary_id": metro_map.get(row['metro1']),
                "time_to_metro_min": int(row['time1']) if not pd.isna(row['time1']) else None,
                "address": str(row.get('address', ''))[:500],
                "clean_address": str(row.get('clean_address', ''))[:500],
                "is_active": True
            })
            
        insert_sql = text("""
            INSERT INTO core.listings (
                item_id, url, title, price, price_per_sqm, total_area, living_area,
                kitchen_area, rooms_count, floor_current, floor_total, is_first_floor,
                is_last_floor, ceiling_height, year_built_unified, condition_unified,
                renovation_cost, object_type, market_type, district_id, metro_primary_id,
                time_to_metro_min, address, clean_address, is_active
            ) VALUES (
                :item_id, :url, :title, :price, :price_per_sqm, :total_area, :living_area,
                :kitchen_area, :rooms_count, :floor_current, :floor_total, :is_first_floor,
                :is_last_floor, :ceiling_height, :year_built_unified, :condition_unified,
                :renovation_cost, :object_type, :market_type, :district_id, :metro_primary_id,
                :time_to_metro_min, :address, :clean_address, :is_active
            )
        """)
        conn.execute(insert_sql, listings_records)
        
        # 4. Log to Data Quality audit table
        conn.execute(
            text("""
                INSERT INTO dq.etl_run_logs (
                    source_file, total_raw_rows, valid_rows_inserted, 
                    duplicates_filtered, inactive_filtered, ceiling_anomalies_fixed, status
                ) VALUES (
                    'avito_listings.xlsx', :raw_rows, :valid_rows,
                    :duplicates, :inactive, :ceil_fixed, 'SUCCESS'
                )
            """),
            {
                "raw_rows": stats['raw_rows'],
                "valid_rows": len(df),
                "duplicates": stats['duplicates_removed'],
                "inactive": stats['inactive_removed'],
                "ceil_fixed": stats['ceiling_anomalies_fixed']
            }
        )
    logger.info(f"PostgreSQL load successful: {len(listings_records)} records inserted.")


def load_to_clickhouse(df: pd.DataFrame, ch_client):
    logger.info("Starting ClickHouse data load...")
    
    # Prepare DataFrame matching mart_avito_bi_flat columns
    ch_df = pd.DataFrame()
    ch_df['item_id'] = df['item_id'].astype('uint64')
    ch_df['url'] = df['url'].astype(str)
    ch_df['title'] = df['title'].astype(str)
    ch_df['price'] = df['price'].astype(float)
    ch_df['price_per_sqm'] = df['price_per_sqm'].astype(float)
    ch_df['total_area'] = df['total_area'].astype('float32')
    ch_df['living_area'] = df['living_area'].astype('float32')
    ch_df['kitchen_area'] = df['kitchen_area'].astype('float32')
    ch_df['kitchen_to_total_ratio'] = df['kitchen_to_total_ratio'].astype('float32')
    ch_df['rooms_count'] = df['rooms_count'].fillna(0).astype('int16')
    ch_df['floor_current'] = df['floor_current'].fillna(0).astype('int16')
    ch_df['floor_total'] = df['floor_total'].fillna(0).astype('int16')
    ch_df['floor_category'] = df['floor_category'].astype(str)
    ch_df['ceiling_height'] = df['ceiling_height'].astype('float32')
    ch_df['year_built_unified'] = df['year_built_unified'].fillna(0).astype('int16')
    ch_df['building_era'] = df['building_era'].astype(str)
    ch_df['condition_unified'] = df['condition_unified'].astype(str)
    ch_df['renovation_cost'] = df['renovation_cost'].astype(float)
    ch_df['renovation_to_price_ratio'] = df['renovation_to_price_ratio'].astype('float32')
    ch_df['object_type'] = df['object_type'].astype(str)
    ch_df['market_type'] = df['market_type'].astype(str)
    ch_df['district'] = df['district'].astype(str)
    ch_df['metro1'] = df['metro1'].astype(str)
    ch_df['time1'] = df['time1'].astype('float32')
    ch_df['metro_time_group'] = df['metro_time_group'].astype(str)
    ch_df['address'] = df.get('address', '').fillna('').astype(str)
    ch_df['clean_address'] = df.get('clean_address', '').fillna('').astype(str)

    # Truncate and insert
    ch_client.command("TRUNCATE TABLE avito_marts.mart_avito_bi_flat")
    ch_client.insert_df(
        table="mart_avito_bi_flat",
        df=ch_df,
        database="avito_marts"
    )
    count = ch_client.command("SELECT count() FROM avito_marts.mart_avito_bi_flat")
    logger.info(f"ClickHouse load successful: {count} records in mart_avito_bi_flat.")


def main():
    data_file = sys.argv[1] if len(sys.argv) > 1 else "data/raw/avito_clean_final_full.xlsx"
    if not os.path.exists(data_file):
        logger.error(f"File not found: {data_file}")
        sys.exit(1)
        
    df_raw = load_raw_data(data_file)
    df_clean, stats = clean_and_transform(df_raw)
    
    # Connect & Load to Postgres
    pg_engine = create_engine(PG_URI)
    load_to_postgres(df_clean, stats, pg_engine)
    
    # Connect & Load to ClickHouse
    ch_client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASS,
        database=CH_DB
    )
    load_to_clickhouse(df_clean, ch_client)
    
    logger.info("=== ETL PIPELINE COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()