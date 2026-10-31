#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Superset metadata user & database
    CREATE USER superset WITH PASSWORD 'superset_password';
    CREATE DATABASE superset OWNER superset;
    GRANT ALL PRIVILEGES ON DATABASE superset TO superset;

    -- Avito DWH user & database
    CREATE USER avito_user WITH PASSWORD 'avito_password';
    CREATE DATABASE avito_dwh OWNER avito_user;
    GRANT ALL PRIVILEGES ON DATABASE avito_dwh TO avito_user;
EOSQL

echo "=== Applying DWH schema to avito_dwh database ==="
if [ -f /docker-entrypoint-initdb.d/02_init_schema.sql ]; then
    psql -v ON_ERROR_STOP=1 --username "avito_user" --dbname "avito_dwh" -f /docker-entrypoint-initdb.d/02_init_schema.sql
fi

