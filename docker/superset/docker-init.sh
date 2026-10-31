#!/bin/bash
set -e

echo "=== [Superset Init] 1. Waiting for PostgreSQL ==="
python -c '
import time, socket, os
host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", 5432))
for i in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print("Postgres is ready!")
            break
    except OSError:
        time.sleep(2)
'

echo "=== [Superset Init] 2. Running db upgrade ==="
superset db upgrade

echo "=== [Superset Init] 3. Creating admin user ==="
superset fab create-admin \
    --username "${ADMIN_USERNAME:-admin}" \
    --firstname Superset \
    --lastname Admin \
    --email "${ADMIN_EMAIL:-admin@avito.ru}" \
    --password "${ADMIN_PASSWORD:-admin}" || true

echo "=== [Superset Init] 4. Initializing Superset roles ==="
superset init

echo "=== [Superset Init] 5. Complete! ==="

