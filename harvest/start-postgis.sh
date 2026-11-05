#!/usr/bin/env bash
# Start a throwaway PostgreSQL with PostGIS for the harvester and the
# equivalence tests, and print its connection string.
#
#   harvest/start-postgis.sh PGBIN DATADIR [PORT]
#
# PGBIN is the bin folder of the geo-registry-postgis environment. Must run as
# an ordinary user (PostgreSQL refuses to run as root). Listens only on a Unix
# socket in DATADIR, with no network port.
set -euo pipefail
pgbin=$1
data=$2
port=${3:-5499}
mkdir -p "$data"
if [ ! -f "$data/PG_VERSION" ]; then
  "$pgbin/initdb" -U postgres -A trust -D "$data" >/dev/null
fi
"$pgbin/pg_ctl" -D "$data" -o "-p $port -k $data -c listen_addresses=''" -l "$data/server.log" -w start >/dev/null
"$pgbin/psql" -X -q -h "$data" -p "$port" -U postgres -d postgres \
  -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS postgis_raster;"
echo "host=$data port=$port user=postgres dbname=postgres"
