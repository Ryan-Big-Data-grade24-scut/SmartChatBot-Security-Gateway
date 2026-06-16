#!/usr/bin/env bash
set -Eeo pipefail

export GAUSSHOME=/usr/local/opengauss
export PATH=$GAUSSHOME/bin:$PATH
export LD_LIBRARY_PATH=$GAUSSHOME/lib:$LD_LIBRARY_PATH
export LANG=en_US.UTF-8

file_env() {
    local var="$1"
    local fileVar="${var}_FILE"
    local def="${2:-}"
    if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
        echo >&2 "error: both $var and $fileVar are set (but are exclusive)"
        exit 1
    fi
    local val="$def"
    if [ "${!var:-}" ]; then
        val="${!var}"
    elif [ "${!fileVar:-}" ]; then
        val="$(< "${!fileVar}")"
    fi
    export "$var"="$val"
    unset "$fileVar"
}

_is_sourced() {
    [ "${#FUNCNAME[@]}" -ge 2 ] \
        && [ "${FUNCNAME[0]}" = '_is_sourced' ] \
        && [ "${FUNCNAME[1]}" = 'source' ]
}

PGDATA="${PGDATA:-/var/lib/opengauss/data}"
export PGDATA

docker_create_db_directories() {
    local user
    user="$(id -u)"
    mkdir -p "$PGDATA"
    chmod 700 "$PGDATA"
    mkdir -p /var/run/opengauss || :
    chmod 775 /var/run/opengauss || :
    if [ "$user" = '0' ]; then
        find "$PGDATA" \! -user omm -exec chown omm '{}' +
        find /var/run/opengauss \! -user omm -exec chown omm '{}' +
    fi
}

docker_init_database_dir() {
    cmdbase="gs_initdb --pwfile=<(echo $GS_PASSWORD) --nodename=gaussdb --encoding=UTF-8 --no-locale --dbcompatibility=PG"
    cmdbase="$cmdbase -D $PGDATA"
    eval "$cmdbase"
}

docker_verify_minimum_env() {
    if [[ "$GS_PASSWORD" =~ ^(.{8,}).*$ ]] && [[ "$GS_PASSWORD" =~ ^(.*[a-z]+).*$ ]] && [[ "$GS_PASSWORD" =~ ^(.*[A-Z]).*$ ]] && [[ "$GS_PASSWORD" =~ ^(.*[0-9]).*$ ]] && [[ "$GS_PASSWORD" =~ ^(.*[#?!@$%^&*-]).*$ ]]; then
        :
    else
        cat >&2 <<- 'EOWARN'
            Error: The supplied GS_PASSWORD is not meet requirements.
            Please Check if the password contains uppercase, lowercase, numbers, special characters, and password length(8).
            At least one uppercase, lowercase, numeric, special character.
            Example: Enmo@123
EOWARN
        exit 1
    fi
    if [ -z "$GS_PASSWORD" ] && [ 'trust' != "${GS_HOST_AUTH_METHOD:-md5}" ]; then
        exit 1
    fi
}

docker_process_init_files() {
    local f
    for f; do
        case "$f" in
            *.sh)
                if [ -x "$f" ]; then
                    echo "$0: running $f"
                    "$f"
                else
                    echo "$0: sourcing $f"
                    . "$f"
                fi
                ;;
            *.sql)    echo "$0: running $f"; gsql -U omm -W "$GS_PASSWORD" -d "$GS_DB" -f "$f"; echo ;;
            *.sql.gz) echo "$0: running $f"; gunzip -c "$f" | gsql -U omm -W "$GS_PASSWORD" -d "$GS_DB"; echo ;;
            *.sql.xz) echo "$0: running $f"; xzcat "$f" | gsql -U omm -W "$GS_PASSWORD" -d "$GS_DB"; echo ;;
            *)        echo "$0: ignoring $f" ;;
        esac
        echo
    done
}

docker_setup_db() {
    if [ "$GS_DB" != 'postgres' ]; then
        gsql -U omm -W "$GS_PASSWORD" -d postgres -c "CREATE DATABASE $GS_DB;" 2>/dev/null || true
        gsql -U omm -W "$GS_PASSWORD" -d postgres -c "CREATE USER gaussdb WITH LOGIN PASSWORD '$GS_PASSWORD';" 2>/dev/null || true
        gsql -U omm -W "$GS_PASSWORD" -d postgres -c "GRANT ALL PRIVILEGES TO gaussdb;" 2>/dev/null || true
    fi
}

docker_setup_user() {
    if [ -n "${GS_USERNAME:-}" ]; then
        gsql -U omm -W "$GS_PASSWORD" -d postgres -c "CREATE USER $GS_USERNAME WITH LOGIN PASSWORD '$GS_PASSWORD';" 2>/dev/null || true
    fi
}

opengauss_setup_hba_conf() {
    echo "" >> "$PGDATA/pg_hba.conf"
    echo "host all all 0.0.0.0/0 ${GS_HOST_AUTH_METHOD:-md5}" >> "$PGDATA/pg_hba.conf"
    echo "host replication gaussdb 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"
}

opengauss_setup_postgresql_conf() {
    {
        echo ""
        echo "wal_level = logical"
        echo "password_encryption_type = 1"
        echo "listen_addresses = '0.0.0.0'"
        echo "max_process_memory=2048MB"
        echo "shared_buffers=64MB"
        echo "wal_buffers=8MB"
        echo "cstore_buffers=64MB"
        if [ -n "${OTHER_PG_CONF:-}" ]; then
            echo -e "$OTHER_PG_CONF"
        fi
    } >> "$PGDATA/postgresql.conf"
}

docker_setup_env() {
    export GS_USER=omm
    file_env 'GS_PASSWORD' 'Enmo@123'
    file_env 'GS_DB' "$GS_USER"
    : "${GS_HOST_AUTH_METHOD:=md5}"
    declare -g DATABASE_ALREADY_EXISTS
    if [ -s "$PGDATA/PG_VERSION" ]; then
        DATABASE_ALREADY_EXISTS='true'
    fi
}

_main() {
    if [ "$1" = 'gaussdb' ]; then
        docker_setup_env
        docker_create_db_directories
        if [ "$(id -u)" = '0' ]; then
            exec gosu omm "$BASH_SOURCE" "$@"
        fi

        if [ -z "$DATABASE_ALREADY_EXISTS" ]; then
            docker_verify_minimum_env
            ls /docker-entrypoint-initdb.d/ > /dev/null 2>&1 || true
            docker_init_database_dir
            opengauss_setup_hba_conf
            opengauss_setup_postgresql_conf

            export PGPASSWORD="${PGPASSWORD:-$GS_PASSWORD}"
            
            echo "Starting temp server in single_node mode..."
            gs_ctl -D "$PGDATA" -Z single_node -o "-c listen_addresses=127.0.0.1 -p 5432" -w start
            
            docker_setup_db
            docker_setup_user
            docker_process_init_files /docker-entrypoint-initdb.d/*

            gs_ctl -D "$PGDATA" -Z single_node -m fast -w stop
            unset PGPASSWORD

            echo
            echo 'openGauss init process complete; ready for start up.'
            echo
        else
            echo 'openGauss Database directory appears to contain a database; Skipping initialization'
        fi
    fi
    exec "$@"
}

if ! _is_sourced; then
    _main "$@"
fi
