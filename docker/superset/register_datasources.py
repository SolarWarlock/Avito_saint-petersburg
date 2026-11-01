"""
Registers ClickHouse & PostgreSQL databases and datasets into Apache Superset metadata.
"""

from superset.app import create_app

app = create_app()

with app.app_context():
    from superset import db
    from superset.models.core import Database
    from superset.connectors.sqla.models import SqlaTable, SqlMetric, TableColumn

    # 1. Register ClickHouse Database
    ch_db = db.session.query(Database).filter_by(database_name="ClickHouse - Avito Marts").first()
    if not ch_db:
        ch_db = Database(
            database_name="ClickHouse - Avito Marts",
            sqlalchemy_uri="clickhousedb://avito_user:avito_password@clickhouse:8123/avito_marts",
            allow_run_async=True,
            allow_ctas=True,
            allow_cvas=True,
            allow_dml=True,
            expose_in_sqllab=True
        )
        db.session.add(ch_db)
        db.session.commit()
        print("Registered 'ClickHouse - Avito Marts' database connection.")
    else:
        print("'ClickHouse - Avito Marts' is already registered.")

    # 2. Register PostgreSQL Database
    pg_db = db.session.query(Database).filter_by(database_name="PostgreSQL - Avito DWH").first()
    if not pg_db:
        pg_db = Database(
            database_name="PostgreSQL - Avito DWH",
            sqlalchemy_uri="postgresql+psycopg2://avito_user:avito_password@postgres:5432/avito_dwh",
            allow_run_async=True,
            allow_ctas=True,
            allow_cvas=True,
            allow_dml=True,
            expose_in_sqllab=True
        )
        db.session.add(pg_db)
        db.session.commit()
        print("Registered 'PostgreSQL - Avito DWH' database connection.")
    else:
        print("'PostgreSQL - Avito DWH' is already registered.")

    # 3. Register ClickHouse Dataset: mart_avito_bi_flat
    dataset = db.session.query(SqlaTable).filter_by(
        table_name="mart_avito_bi_flat",
        database_id=ch_db.id
    ).first()

    if not dataset:
        dataset = SqlaTable(
            table_name="mart_avito_bi_flat",
            schema="avito_marts",
            database=ch_db
        )
        db.session.add(dataset)
        db.session.commit()
        print("Registered 'mart_avito_bi_flat' dataset.")

        # Fetch columns from table
        try:
            dataset.fetch_metadata()
            db.session.commit()
            print("Fetched metadata columns for 'mart_avito_bi_flat'.")
        except Exception as e:
            print(f"Metadata fetch warning: {e}")

    # Add custom analytical metrics
    existing_metrics = {m.metric_name for m in dataset.metrics}
    metrics_to_add = [
        ("listings_count", "count()", "Количество объявлений"),
        ("median_price_per_sqm", "medianExact(price_per_sqm)", "Медианная цена за м² (₽)"),
        ("avg_price_per_sqm", "round(avg(price_per_sqm))", "Средняя цена за м² (₽)"),
        ("median_total_price", "medianExact(price)", "Медианная стоимость квартиры (₽)"),
        ("median_area", "medianExact(total_area)", "Медианная площадь (м²)"),
        ("avg_renovation_cost", "round(avg(renovation_cost))", "Средняя стоимость ремонта (₽)")
    ]

    for m_name, m_expr, m_desc in metrics_to_add:
        if m_name not in existing_metrics:
            metric = SqlMetric(
                metric_name=m_name,
                expression=m_expr,
                verbose_name=m_desc,
                table=dataset
            )
            db.session.add(metric)
            print(f"Added metric: {m_name} ({m_desc})")

    db.session.commit()

    # 4. Register ClickHouse Dataset: mart_underpriced_deals
    deals_dataset = db.session.query(SqlaTable).filter_by(
        table_name="mart_underpriced_deals",
        database_id=ch_db.id
    ).first()

    if not deals_dataset:
        deals_dataset = SqlaTable(
            table_name="mart_underpriced_deals",
            schema="avito_marts",
            database=ch_db
        )
        db.session.add(deals_dataset)
        db.session.commit()
        print("Registered 'mart_underpriced_deals' dataset.")

        try:
            deals_dataset.fetch_metadata()
            db.session.commit()
            print("Fetched metadata columns for 'mart_underpriced_deals'.")
        except Exception as e:
            print(f"Metadata fetch warning: {e}")

    # Add custom metrics for underpriced deals
    existing_deal_metrics = {m.metric_name for m in deals_dataset.metrics}
    deal_metrics_to_add = [
        ("deals_count", "count()", "Число найденных лотов"),
        ("avg_discount_pct", "round(avg(discount_pct), 1)", "Средний дисконт к району (%)"),
        ("max_discount_pct", "round(max(discount_pct), 1)", "Максимальный дисконт (%)"),
        ("total_potential_gain", "round(sum(potential_gain_rub))", "Суммарный инвестиционный потенциал (₽)")
    ]
    for m_name, m_expr, m_desc in deal_metrics_to_add:
        if m_name not in existing_deal_metrics:
            metric = SqlMetric(
                metric_name=m_name,
                expression=m_expr,
                verbose_name=m_desc,
                table=deals_dataset
            )
            db.session.add(metric)
            print(f"Added metric: {m_name} ({m_desc})")

    db.session.commit()

    # 5. Register ClickHouse Dataset: mart_floor_penalty_matrix
    floor_dataset = db.session.query(SqlaTable).filter_by(
        table_name="mart_floor_penalty_matrix",
        database_id=ch_db.id
    ).first()

    if not floor_dataset:
        floor_dataset = SqlaTable(
            table_name="mart_floor_penalty_matrix",
            schema="avito_marts",
            database=ch_db
        )
        db.session.add(floor_dataset)
        db.session.commit()
        print("Registered 'mart_floor_penalty_matrix' dataset.")

        try:
            floor_dataset.fetch_metadata()
            db.session.commit()
            print("Fetched metadata columns for 'mart_floor_penalty_matrix'.")
        except Exception as e:
            print(f"Metadata fetch warning: {e}")

    db.session.commit()
    print("All databases and dataset metrics configured successfully in Superset!")


