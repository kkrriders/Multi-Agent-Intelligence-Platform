#!/bin/sh
set -e
DB_DIR="${DB_DIR:-/db}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-/migrations}"
PSQL="psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB"

$PSQL -c "create role maip_app login password '$MAIP_APP_PASSWORD'"
$PSQL -f "$DB_DIR/00_local_shim.sql"
for f in "$MIGRATIONS_DIR"/*.sql; do
  echo "applying $f"
  $PSQL -f "$f"
done

$PSQL <<'SQL'
grant usage on schema public, auth, storage to maip_app;
grant select, insert, update, delete on all tables in schema public to maip_app;
grant select, insert on auth.users to maip_app;
grant select on storage.buckets to maip_app;
grant select, insert, update, delete on storage.objects to maip_app;
grant execute on function auth.uid() to maip_app;
grant execute on function storage.foldername(text) to maip_app;
SQL
