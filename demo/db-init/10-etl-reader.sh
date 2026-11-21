#!/bin/sh
# Mínimo privilegio: el ETL lee con un usuario que SOLO puede hacer SELECT.
# Se ejecuta una sola vez, al crear la base por primera vez.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE etl_reader LOGIN PASSWORD '${ETL_READER_PASSWORD}';
GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO etl_reader;
GRANT USAGE ON SCHEMA public TO etl_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public GRANT SELECT ON TABLES TO etl_reader;
SQL
