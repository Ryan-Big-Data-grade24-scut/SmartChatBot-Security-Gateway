#!/usr/bin/env bash
set -Eeo pipefail

export GAUSSHOME=/usr/local/opengauss
export PATH=$GAUSSHOME/bin:$PATH
export LD_LIBRARY_PATH=$GAUSSHOME/lib:$LD_LIBRARY_PATH
export LANG=en_US.UTF-8
PGDATA="${PGDATA:-/var/lib/opengauss/data}"

_main() {
    GS_PASSWORD="${GS_PASSWORD:-Enmo@123}"
    GS_DB="${GS_DB:-postgres}"
    GS_HOST_AUTH_METHOD="${GS_HOST_AUTH_METHOD:-md5}"

    if [ "$(id -u)" = '0' ]; then
        mkdir -p "$PGDATA"
        chown omm:omm "$PGDATA"
        chmod 700 "$PGDATA"
        exec gosu omm "$BASH_SOURCE" "$@"
    fi

    if [ ! -s "$PGDATA/PG_VERSION" ]; then
        echo "Initializing openGauss database..."
        gs_initdb --pwfile=<(echo $GS_PASSWORD) --nodename=gaussdb --encoding=UTF-8 --no-locale --dbcompatibility=PG -D "$PGDATA" 2>&1

        cat >> "$PGDATA/postgresql.conf" <<-EOC
listen_addresses = '0.0.0.0'
password_encryption_type = 1
wal_level = logical
EOC

        echo "host all all 0.0.0.0/0 ${GS_HOST_AUTH_METHOD}" >> "$PGDATA/pg_hba.conf"
    fi

    # Start openGauss in foreground
    echo "Starting openGauss..."
    exec gaussdb -D "$PGDATA" --single_node -p 5432
}

_main "$@"
