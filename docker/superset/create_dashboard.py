"""
Automated Dashboard & Chart Generation for Apache Superset
Creates the complete Avito Real Estate Analytics Dashboard structure.
"""

import json
from superset.app import create_app

app = create_app()

with app.app_context():
    from superset import db
    from superset.models.slice import Slice
    from superset.models.dashboard import Dashboard
    from superset.connectors.sqla.models import SqlaTable

    # 1. Fetch the dataset
    table = db.session.query(SqlaTable).filter_by(table_name="mart_avito_bi_flat").first()
    if not table:
        raise ValueError("Dataset 'mart_avito_bi_flat' not found in Superset!")

    dataset_id = table.id
    print(f"Using dataset: {table.table_name} (ID: {dataset_id})")

    # 2. Define All Charts
    charts_def = [
        # --- ROW 1: KPIs ---
        {
            "slice_name": "Всего проверенных объявлений",
            "viz_type": "big_number_total",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "big_number_total",
                "metric": "listings_count",
                "subheader": "Уникальные объекты после дедупликации",
                "y_axis_format": ",d",
                "time_range": "No filter"
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "metrics": ["listings_count"],
                    "is_timeseries": False
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },
        {
            "slice_name": "Медианная цена кв. метра",
            "viz_type": "big_number_total",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "big_number_total",
                "metric": "median_price_per_sqm",
                "subheader": "Рублей за 1 м²",
                "y_axis_format": ",.0f",
                "time_range": "No filter"
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "metrics": ["median_price_per_sqm"],
                    "is_timeseries": False
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },
        {
            "slice_name": "Медианный бюджет квартиры",
            "viz_type": "big_number_total",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "big_number_total",
                "metric": "median_total_price",
                "subheader": "Медианная стоимость объекта",
                "y_axis_format": ",.0f",
                "time_range": "No filter"
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "metrics": ["median_total_price"],
                    "is_timeseries": False
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },
        {
            "slice_name": "Медианная площадь жилья",
            "viz_type": "big_number_total",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "big_number_total",
                "metric": "median_area",
                "subheader": "Квадратных метров (м²)",
                "y_axis_format": ".1f",
                "time_range": "No filter"
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "metrics": ["median_area"],
                    "is_timeseries": False
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },

        # --- ROW 2: Primary Analytics ---
        {
            "slice_name": "Медианная стоимость м² по районам СПб",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "echarts_timeseries_bar",
                "x_axis": "district",
                "time_grain_sqla": None,
                "granularity_sqla": "loaded_at",
                "time_range": "No filter",
                "metrics": ["median_price_per_sqm"],
                "groupby": [],
                "orientation": "vertical",
                "show_value": True,
                "y_axis_format": ",.0f",
                "x_axis_title": "Район Санкт-Петербурга",
                "y_axis_title": "Медиана ₽ / м²",
                "order_desc": True
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "columns": ["district"],
                    "metrics": ["median_price_per_sqm"],
                    "orderby": [["median_price_per_sqm", False]],
                    "order_desc": True,
                    "row_limit": 100,
                    "is_timeseries": False,
                    "post_processing": [{"operation": "flatten"}]
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },
        {
            "slice_name": "Структура предложения по комнатности",
            "viz_type": "pie",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "pie",
                "metric": "listings_count",
                "groupby": ["rooms_count"],
                "donut": True,
                "show_labels": True,
                "labels_type": "key_percent",
                "time_range": "No filter"
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "columns": ["rooms_count"],
                    "metrics": ["listings_count"],
                    "is_timeseries": False
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },

        # --- ROW 3: Metro & Building Era ---
        {
            "slice_name": "Влияние удаленности от метро на цену м²",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "echarts_timeseries_bar",
                "x_axis": "metro_time_group",
                "time_grain_sqla": None,
                "granularity_sqla": "loaded_at",
                "time_range": "No filter",
                "metrics": ["median_price_per_sqm"],
                "groupby": [],
                "orientation": "vertical",
                "show_value": True,
                "y_axis_format": ",.0f",
                "x_axis_title": "Время пешком до метро",
                "y_axis_title": "Медиана ₽ / м²",
                "order_desc": True
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "columns": ["metro_time_group"],
                    "metrics": ["median_price_per_sqm"],
                    "orderby": [["median_price_per_sqm", False]],
                    "order_desc": True,
                    "row_limit": 100,
                    "is_timeseries": False,
                    "post_processing": [{"operation": "flatten"}]
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },
        {
            "slice_name": "Цены м² по эпохам постройки",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "echarts_timeseries_bar",
                "x_axis": "building_era",
                "time_grain_sqla": None,
                "granularity_sqla": "loaded_at",
                "time_range": "No filter",
                "metrics": ["median_price_per_sqm"],
                "groupby": [],
                "orientation": "vertical",
                "show_value": True,
                "y_axis_format": ",.0f",
                "x_axis_title": "Период постройки",
                "y_axis_title": "Медиана ₽ / м²",
                "order_desc": True
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "columns": ["building_era"],
                    "metrics": ["median_price_per_sqm"],
                    "orderby": [["median_price_per_sqm", False]],
                    "order_desc": True,
                    "row_limit": 100,
                    "is_timeseries": False,
                    "post_processing": [{"operation": "flatten"}]
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },

        # --- ROW 4: Renovation & Metro Leaderboard ---
        {
            "slice_name": "Премия за ремонт (цена м² по состоянию)",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "echarts_timeseries_bar",
                "x_axis": "condition_unified",
                "time_grain_sqla": None,
                "granularity_sqla": "loaded_at",
                "time_range": "No filter",
                "metrics": ["median_price_per_sqm"],
                "groupby": [],
                "orientation": "vertical",
                "show_value": True,
                "y_axis_format": ",.0f",
                "x_axis_title": "Тип отделки / ремонта",
                "y_axis_title": "Медиана ₽ / м²",
                "order_desc": True
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "columns": ["condition_unified"],
                    "metrics": ["median_price_per_sqm"],
                    "orderby": [["median_price_per_sqm", False]],
                    "order_desc": True,
                    "row_limit": 100,
                    "is_timeseries": False,
                    "post_processing": [{"operation": "flatten"}]
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },
        {
            "slice_name": "Топ-15 станций метро по стоимости кв. метра",
            "viz_type": "table",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "table",
                "groupby": ["metro1"],
                "metrics": ["median_price_per_sqm", "listings_count", "median_total_price"],
                "row_limit": 15,
                "order_desc": True,
                "include_search": True,
                "time_range": "No filter"
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "columns": ["metro1"],
                    "metrics": ["median_price_per_sqm", "listings_count", "median_total_price"],
                    "orderby": [["median_price_per_sqm", False]],
                    "order_desc": True,
                    "row_limit": 15,
                    "is_timeseries": False
                }],
                "result_format": "json",
                "result_type": "full"
            }
        },

        # --- ROW 5: Detailed Listings Grid ---
        {
            "slice_name": "Реестр объявлений (с детализацией параметров)",
            "viz_type": "table",
            "params": {
                "datasource": f"{dataset_id}__table",
                "viz_type": "table",
                "all_columns": [
                    "item_id", "title", "district", "metro1", "time1", 
                    "price", "price_per_sqm", "total_area", "rooms_count", 
                    "condition_unified", "building_era", "market_type", "object_type"
                ],
                "order_by_cols": ['["price_per_sqm", false]'],
                "row_limit": 50,
                "include_search": True,
                "table_timestamp_format": "smart_date",
                "time_range": "No filter"
            },
            "query_context": {
                "datasource": {"id": dataset_id, "type": "table"},
                "force": False,
                "queries": [{
                    "columns": [
                        "item_id", "title", "district", "metro1", "time1", 
                        "price", "price_per_sqm", "total_area", "rooms_count", 
                        "condition_unified", "building_era", "market_type", "object_type"
                    ],
                    "orderby": [["price_per_sqm", False]],
                    "order_desc": True,
                    "row_limit": 50,
                    "is_timeseries": False
                }],
                "result_format": "json",
                "result_type": "full"
            }
        }
    ]

    created_slices = []
    for c_def in charts_def:
        slice_obj = db.session.query(Slice).filter_by(slice_name=c_def["slice_name"]).first()
        qc_dict = c_def.get("query_context")
        if qc_dict:
            qc_dict["form_data"] = c_def["params"]
            qc_json = json.dumps(qc_dict)
        else:
            qc_json = None

        if not slice_obj:
            slice_obj = Slice(
                slice_name=c_def["slice_name"],
                viz_type=c_def["viz_type"],
                datasource_type="table",
                datasource_id=dataset_id,
                params=json.dumps(c_def["params"]),
                query_context=qc_json
            )
            db.session.add(slice_obj)
            db.session.commit()
            print(f"Created Chart: {slice_obj.slice_name} (ID: {slice_obj.id})")
        else:
            slice_obj.params = json.dumps(c_def["params"])
            slice_obj.viz_type = c_def["viz_type"]
            slice_obj.query_context = qc_json
            db.session.commit()
            print(f"Updated Chart: {slice_obj.slice_name} (ID: {slice_obj.id})")
        created_slices.append(slice_obj)

    # 3. Assemble Dashboard Layout exactly matching Superset v2 schema
    kpi_slices = created_slices[0:4]
    market_slices = created_slices[4:6]
    metro_era_slices = created_slices[6:8]
    reno_top_slices = created_slices[8:10]
    table_slice = created_slices[10]

    position_data = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {
            "children": ["GRID_ID"],
            "id": "ROOT_ID",
            "type": "ROOT"
        },
        "HEADER_ID": {
            "id": "HEADER_ID",
            "meta": {
                "text": "Авито Недвижимость — Анализ рынка жилья (Санкт-Петербург)"
            },
            "type": "HEADER"
        },
        "GRID_ID": {
            "children": [
                "ROW-header",
                "ROW-kpis",
                "ROW-market",
                "ROW-metro-era",
                "ROW-reno-top",
                "ROW-table"
            ],
            "id": "GRID_ID",
            "parents": ["ROOT_ID"],
            "type": "GRID"
        },
        "ROW-header": {
            "children": ["MARKDOWN-header"],
            "id": "ROW-header",
            "meta": {
                "background": "BACKGROUND_TRANSPARENT"
            },
            "parents": ["ROOT_ID", "GRID_ID"],
            "type": "ROW"
        },
        "MARKDOWN-header": {
            "children": [],
            "id": "MARKDOWN-header",
            "meta": {
                "code": "### 🏠 Авито Недвижимость: Мониторинг рынка жилья и ценообразования (Санкт-Петербург)\n*Аналитическая витрина DWH на стеке PostgreSQL 15 + ClickHouse MergeTree + Apache Superset. Очищено от выбросов и дедуплицировано по естественному `item_id`.*",
                "height": 20,
                "width": 12
            },
            "parents": ["ROOT_ID", "GRID_ID", "ROW-header"],
            "type": "MARKDOWN"
        }
    }

    # Helper to add standard chart rows
    def add_chart_row(row_id, slice_width_pairs):
        children = []
        for sl, w in slice_width_pairs:
            chart_key = f"CHART-{sl.id}"
            children.append(chart_key)
            position_data[chart_key] = {
                "children": [],
                "id": chart_key,
                "meta": {
                    "chartId": sl.id,
                    "height": 50,
                    "sliceName": sl.slice_name,
                    "width": w
                },
                "parents": ["ROOT_ID", "GRID_ID", row_id],
                "type": "CHART"
            }
        position_data[row_id] = {
            "children": children,
            "id": row_id,
            "meta": {
                "background": "BACKGROUND_TRANSPARENT"
            },
            "parents": ["ROOT_ID", "GRID_ID"],
            "type": "ROW"
        }

    add_chart_row("ROW-kpis", [(s, 3) for s in kpi_slices])
    add_chart_row("ROW-market", [(market_slices[0], 8), (market_slices[1], 4)])
    add_chart_row("ROW-metro-era", [(metro_era_slices[0], 6), (metro_era_slices[1], 6)])
    add_chart_row("ROW-reno-top", [(reno_top_slices[0], 6), (reno_top_slices[1], 6)])
    add_chart_row("ROW-table", [(table_slice, 12)])

    # 4. Clean Dashboard Metadata
    dashboard_metadata = {
        "timed_refresh_immune_slices": [],
        "expanded_slices": {},
        "refresh_frequency": 0,
        "default_filters": "{}",
        "color_scheme": "supersetColors",
        "chart_configuration": {}
    }

    # 5. Create or Update Dashboard
    dash_title = "Авито Недвижимость — Анализ рынка жилья (Санкт-Петербург)"
    dash_slug = "avito-spb-real-estate"
    dashboard = db.session.query(Dashboard).filter_by(slug=dash_slug).first()

    if not dashboard:
        dashboard = Dashboard(
            dashboard_title=dash_title,
            slug=dash_slug,
            published=True,
            position_json=json.dumps(position_data),
            json_metadata=json.dumps(dashboard_metadata),
            slices=created_slices
        )
        db.session.add(dashboard)
        db.session.commit()
        print(f"Created Dashboard '{dashboard.dashboard_title}' (ID: {dashboard.id}, URL: /superset/dashboard/{dash_slug}/)")
    else:
        dashboard.dashboard_title = dash_title
        dashboard.published = True
        dashboard.position_json = json.dumps(position_data)
        dashboard.json_metadata = json.dumps(dashboard_metadata)
        dashboard.slices = created_slices
        db.session.commit()
        print(f"Updated Dashboard '{dashboard.dashboard_title}' (ID: {dashboard.id}, URL: /superset/dashboard/{dash_slug}/)")

    print("=== DASHBOARD SETUP COMPLETED SUCCESSFULLY ===")
