"""
Automated Dashboard & Chart Generation for Apache Superset
Creates the complete Avito Real Estate Analytics Dashboard with:
- Avito corporate branding (colors, modern custom CSS, hero banner)
- Interactive Native Filter Bar (District, Rooms, Market Type, Object Type, Era, Metro Distance, Price Range)
- Full Cross-Filtering across charts
- Polished chart axes without label collision
"""

import json
from superset.app import create_app

app = create_app()

with app.app_context():
    from superset import db
    from superset.models.slice import Slice
    from superset.models.dashboard import Dashboard
    from superset.connectors.sqla.models import SqlaTable

    # 1. Fetch the ClickHouse BI dataset
    table = db.session.query(SqlaTable).filter_by(table_name="mart_avito_bi_flat").first()
    if not table:
        raise ValueError("Dataset 'mart_avito_bi_flat' not found in Superset!")

    dataset_id = table.id
    dataset_uuid = str(table.uuid)
    print(f"Using dataset: {table.table_name} (ID: {dataset_id}, UUID: {dataset_uuid})")

    # 2. Define All Slices
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
                "subheader": "Рублей за 1 м² жилья",
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
                "subheader": "Медианная стоимость квартиры",
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
                "x_axis_title_margin": 65,
                "y_axis_title": "Медиана ₽ / м²",
                "y_axis_title_margin": 65,
                "y_axis_title_position": "Left",
                "xAxisLabelRotation": -35,
                "xAxisLabelInterval": 0,
                "truncateXAxis": False,
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
                "x_axis_title_margin": 50,
                "y_axis_title": "Медиана ₽ / м²",
                "y_axis_title_margin": 65,
                "y_axis_title_position": "Left",
                "xAxisLabelRotation": 0,
                "xAxisLabelInterval": 0,
                "truncateXAxis": False,
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
                "x_axis_title_margin": 75,
                "y_axis_title": "Медиана ₽ / м²",
                "y_axis_title_margin": 65,
                "y_axis_title_position": "Left",
                "xAxisLabelRotation": 0,
                "xAxisLabelInterval": 0,
                "truncateXAxis": False,
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
                "x_axis_title_margin": 75,
                "y_axis_title": "Медиана ₽ / м²",
                "y_axis_title_margin": 65,
                "y_axis_title_position": "Left",
                "xAxisLabelRotation": 0,
                "xAxisLabelInterval": 0,
                "truncateXAxis": False,
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
            "slice_name": "Реестр объявлений с детализацией параметров",
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

    chart_ids = [s.id for s in created_slices]

    # 3. Assemble Dashboard Layout
    kpi_slices = created_slices[0:4]
    market_slices = created_slices[4:6]
    metro_era_slices = created_slices[6:8]
    reno_top_slices = created_slices[8:10]
    table_slice = created_slices[10]

    header_html = (
        '<div style="background: linear-gradient(135deg, #0077CC 0%, #00AAFF 60%, #00C48C 100%); '
        'border-radius: 12px; padding: 20px 24px; color: #ffffff; '
        'box-shadow: 0 4px 20px rgba(0, 170, 255, 0.22); '
        'display: flex; justify-content: space-between; align-items: center;">'
        '  <div>'
        '    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">'
        '      <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #97D700; box-shadow: 0 0 6px #97D700;"></span>'
        '      <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #FF335F; box-shadow: 0 0 6px #FF335F;"></span>'
        '      <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #A521FF; box-shadow: 0 0 6px #A521FF;"></span>'
        '      <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #FFB703; box-shadow: 0 0 6px #FFB703;"></span>'
        '      <span style="font-size: 12px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: rgba(255,255,255,0.95); margin-left: 6px;">АВИТО НЕДВИЖИМОСТЬ &bull; САНКТ-ПЕТЕРБУРГ</span>'
        '    </div>'
        '    <h1 style="margin: 0; font-size: 23px; font-weight: 800; color: #ffffff; letter-spacing: -0.3px;">Мониторинг рынка жилой недвижимости Санкт-Петербурга</h1>'
        '    <div style="margin-top: 5px; font-size: 13px; color: rgba(255,255,255,0.92);">'
        '      <strong>30 994 валидированных объекта</strong> без дублей и аномалий. Выберите фильтры на левой панели для интерактивного анализа.'
        '    </div>'
        '  </div>'
        '</div>'
    )

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
                "text": "Авито Недвижимость - Анализ рынка жилья Санкт-Петербурга"
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
                "code": header_html,
                "height": 12,
                "width": 12
            },
            "parents": ["ROOT_ID", "GRID_ID", "ROW-header"],
            "type": "MARKDOWN"
        }
    }

    # Helper to add standard chart rows
    def add_chart_row(row_id, slice_width_pairs, row_height=52):
        children = []
        for sl, w in slice_width_pairs:
            chart_key = f"CHART-{sl.id}"
            children.append(chart_key)
            position_data[chart_key] = {
                "children": [],
                "id": chart_key,
                "meta": {
                    "chartId": sl.id,
                    "height": row_height,
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

    add_chart_row("ROW-kpis", [(s, 3) for s in kpi_slices], row_height=30)
    add_chart_row("ROW-market", [(market_slices[0], 8), (market_slices[1], 4)], row_height=54)
    add_chart_row("ROW-metro-era", [(metro_era_slices[0], 6), (metro_era_slices[1], 6)], row_height=54)
    add_chart_row("ROW-reno-top", [(reno_top_slices[0], 6), (reno_top_slices[1], 6)], row_height=54)
    add_chart_row("ROW-table", [(table_slice, 12)], row_height=65)

    # 4. Native Filter Configuration
    native_filters = [
        {
            "id": "NATIVE_FILTER-district",
            "name": "Район СПб",
            "filterType": "filter_select",
            "targets": [
                {
                    "datasetId": dataset_id,
                    "datasetUuid": dataset_uuid,
                    "column": {"name": "district"}
                }
            ],
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
            "controlValues": {
                "defaultToFirstItem": False,
                "enableEmptyFilter": False,
                "inverseSelection": False,
                "multiSelect": True,
                "searchAllOptions": True
            },
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
            "type": "NATIVE_FILTER",
            "description": "Административный район Санкт-Петербурга"
        },
        {
            "id": "NATIVE_FILTER-rooms_count",
            "name": "Комнатность",
            "filterType": "filter_select",
            "targets": [
                {
                    "datasetId": dataset_id,
                    "datasetUuid": dataset_uuid,
                    "column": {"name": "rooms_count"}
                }
            ],
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
            "controlValues": {
                "defaultToFirstItem": False,
                "enableEmptyFilter": False,
                "inverseSelection": False,
                "multiSelect": True,
                "searchAllOptions": True
            },
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
            "type": "NATIVE_FILTER",
            "description": "Число комнат: 0 (студия), 1, 2, 3, 4+"
        },
        {
            "id": "NATIVE_FILTER-market_type",
            "name": "Тип рынка",
            "filterType": "filter_select",
            "targets": [
                {
                    "datasetId": dataset_id,
                    "datasetUuid": dataset_uuid,
                    "column": {"name": "market_type"}
                }
            ],
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
            "controlValues": {
                "defaultToFirstItem": False,
                "enableEmptyFilter": False,
                "inverseSelection": False,
                "multiSelect": True,
                "searchAllOptions": True
            },
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
            "type": "NATIVE_FILTER",
            "description": "Вторичка или Новостройка"
        },
        {
            "id": "NATIVE_FILTER-object_type",
            "name": "Тип объекта",
            "filterType": "filter_select",
            "targets": [
                {
                    "datasetId": dataset_id,
                    "datasetUuid": dataset_uuid,
                    "column": {"name": "object_type"}
                }
            ],
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
            "controlValues": {
                "defaultToFirstItem": False,
                "enableEmptyFilter": False,
                "inverseSelection": False,
                "multiSelect": True,
                "searchAllOptions": True
            },
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
            "type": "NATIVE_FILTER",
            "description": "Квартира, Апартаменты, Доля"
        },
        {
            "id": "NATIVE_FILTER-building_era",
            "name": "Эпоха постройки",
            "filterType": "filter_select",
            "targets": [
                {
                    "datasetId": dataset_id,
                    "datasetUuid": dataset_uuid,
                    "column": {"name": "building_era"}
                }
            ],
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
            "controlValues": {
                "defaultToFirstItem": False,
                "enableEmptyFilter": False,
                "inverseSelection": False,
                "multiSelect": True,
                "searchAllOptions": True
            },
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
            "type": "NATIVE_FILTER",
            "description": "Новый фонд (>2015), Советский, Современный, Дореволюционный"
        },
        {
            "id": "NATIVE_FILTER-metro_time_group",
            "name": "Удаленность от метро",
            "filterType": "filter_select",
            "targets": [
                {
                    "datasetId": dataset_id,
                    "datasetUuid": dataset_uuid,
                    "column": {"name": "metro_time_group"}
                }
            ],
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
            "controlValues": {
                "defaultToFirstItem": False,
                "enableEmptyFilter": False,
                "inverseSelection": False,
                "multiSelect": True,
                "searchAllOptions": True
            },
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
            "type": "NATIVE_FILTER",
            "description": "Пешая доступность до ближайшей станции метро"
        },
        {
            "id": "NATIVE_FILTER-price_per_sqm",
            "name": "Цена за м² (₽)",
            "filterType": "filter_range",
            "targets": [
                {
                    "datasetId": dataset_id,
                    "datasetUuid": dataset_uuid,
                    "column": {"name": "price_per_sqm"}
                }
            ],
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
            "controlValues": {"enableEmptyFilter": False},
            "cascadeParentIds": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
            "type": "NATIVE_FILTER",
            "description": "Диапазон стоимости одного квадратного метра"
        }
    ]

    # Cross-filtering configuration for interactive drilldown
    chart_configuration = {}
    for s in created_slices:
        other_ids = [o.id for o in created_slices if o.id != s.id]
        chart_configuration[str(s.id)] = {
            "id": s.id,
            "crossFilters": {
                "scope": "global",
                "chartsInScope": other_ids
            }
        }

    # Avito Palette & Styling Metadata
    dashboard_metadata = {
        "timed_refresh_immune_slices": [],
        "expanded_slices": {},
        "refresh_frequency": 0,
        "default_filters": "{}",
        "color_scheme": "supersetColors",
        "color_scheme_domain": [
            "#00AAFF",  # Avito Blue
            "#97D700",  # Avito Green
            "#FF335F",  # Avito Coral/Red
            "#A521FF",  # Avito Violet
            "#FFB703",  # Avito Amber
            "#00C48C",  # Teal Accent
            "#454E7C",  # Slate Navy
            "#A868B7",  # Soft Purple
            "#FF7F44",  # Sunset Orange
            "#2A2A2A"   # Charcoal
        ],
        "label_colors": {
            "Медианная цена за м² (₽)": "#00AAFF",
            "listings_count": "#00AAFF",
            "median_total_price": "#97D700",
            "1": "#00AAFF",
            "2": "#97D700",
            "0": "#FFB703",
            "3": "#FF335F",
            "4": "#A521FF",
            "5": "#00C48C",
            "6": "#454E7C",
            "Вторичка": "#00AAFF",
            "Новостройка": "#97D700"
        },
        "cross_filters_enabled": True,
        "global_chart_configuration": {
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids
        },
        "chart_configuration": chart_configuration,
        "native_filter_configuration": native_filters
    }

    # 5. Modern Avito Custom CSS
    avito_css = """
/* =========================================================
   AVITO BRAND THEME STYLING
   ========================================================= */

/* Global Page Background and Font */
body {
    background-color: #F4F6F9 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
}

/* Dashboard Top Header Bar */
.dashboard-header {
    background: #FFFFFF !important;
    border-bottom: 3px solid #00AAFF !important;
    box-shadow: 0 2px 10px rgba(0, 170, 255, 0.08) !important;
    padding: 14px 28px !important;
}

.dashboard-header .header-title {
    font-weight: 800 !important;
    color: #1A1F2C !important;
    font-size: 20px !important;
}

/* Chart and Markdown Cards */
.dashboard-component-chart-holder {
    background: #FFFFFF !important;
    border-radius: 12px !important;
    border: 1px solid #E5E7EB !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    padding: 8px !important;
}

.dashboard-component-chart-holder:hover {
    box-shadow: 0 8px 24px rgba(0, 170, 255, 0.12) !important;
    border-color: #BAE7FF !important;
}

/* Chart Title Headers */
.dashboard-component-chart-holder .header-title {
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #1F2937 !important;
    letter-spacing: -0.2px !important;
}

/* Big Number KPI Metrics */
.slice_container .big-number {
    font-size: 38px !important;
    font-weight: 800 !important;
    color: #00AAFF !important;
    letter-spacing: -1px !important;
}

.slice_container .subheader {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
    margin-top: 4px !important;
}

/* Native Filters Sidebar */
.dashboard-filter-bar {
    background: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
    box-shadow: 3px 0 15px rgba(0, 0, 0, 0.03) !important;
}

.filter-bar-header {
    font-weight: 700 !important;
    color: #111827 !important;
    border-bottom: 2px solid #00AAFF !important;
    padding-bottom: 10px !important;
}

/* Primary Action Buttons */
.ant-btn-primary {
    background-color: #00AAFF !important;
    border-color: #00AAFF !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(0, 170, 255, 0.3) !important;
}

.ant-btn-primary:hover, .ant-btn-primary:focus {
    background-color: #0088CC !important;
    border-color: #0088CC !important;
}

/* Table Enhancements */
.table-condensed th {
    background-color: #F8FAFC !important;
    color: #374151 !important;
    font-weight: 700 !important;
    border-bottom: 2px solid #E5E7EB !important;
}

.table-condensed tr:hover td {
    background-color: #F0F9FF !important;
}
"""

    # 6. Create or Update Dashboard Record
    dash_title = "Авито Недвижимость - Анализ рынка жилья Санкт-Петербурга"
    dash_slug = "avito-spb-real-estate"
    dashboard = db.session.query(Dashboard).filter_by(slug=dash_slug).first()

    if not dashboard:
        dashboard = Dashboard(
            dashboard_title=dash_title,
            slug=dash_slug,
            published=True,
            position_json=json.dumps(position_data),
            json_metadata=json.dumps(dashboard_metadata),
            css=avito_css,
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
        dashboard.css = avito_css
        dashboard.slices = created_slices
        db.session.commit()
        print(f"Updated Dashboard '{dashboard.dashboard_title}' (ID: {dashboard.id}, URL: /superset/dashboard/{dash_slug}/)")

    print("=== AVITO BRAND STYLING & NATIVE FILTERS CONFIGURED SUCCESSFULLY ===")
