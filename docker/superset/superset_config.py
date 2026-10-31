import os
from datetime import timedelta

# ---------------------------------------------------------
# Superset specific config
# ---------------------------------------------------------
ROW_LIMIT = 50000
SUPERSET_WORKERS = 2
SUPERSET_WEBSERVER_PORT = 8088

# ---------------------------------------------------------
# Flask App Builder configuration
# ---------------------------------------------------------
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "avito_bootcamp_super_secret_key_2026")

# Database connection for Superset metadata
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "postgresql+psycopg2://superset:superset_password@postgres:5432/superset"
)

# ---------------------------------------------------------
# Cache & Async query execution with Redis
# ---------------------------------------------------------
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")

CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_cache_',
    'CACHE_REDIS_URL': f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
}
DATA_CACHE_CONFIG = CACHE_CONFIG

# ---------------------------------------------------------
# Feature flags
# ---------------------------------------------------------
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "GENERIC_CHART_AXES": True,
    "ALERT_REPORTS": False
}

TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = False
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': ['*']
}

