FROM apache/superset:latest

USER root

# Install ClickHouse connector and PostgreSQL driver into Superset venv
RUN uv pip install --python /app/.venv clickhouse-connect psycopg2-binary

USER superset
