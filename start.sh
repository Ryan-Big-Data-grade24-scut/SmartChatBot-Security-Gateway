#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/venv"
BACKEND_DIR="$PROJECT_DIR/backend"
BACKEND_LOG="/tmp/backend.log"
PID_FILE="/tmp/backend.pid"

export DEEPSEEK_API_KEY="sk-ee53aaf753c24e63a23c3b87fd6e32ce"
export DEEPSEEK_BASE_URL="https://api.deepseek.com/v1"
export DEEPSEEK_MODEL="deepseek-chat"

start() {
    echo ">>> Starting SmartChatBot..."

    echo "[1/3] Starting PostgreSQL..."
    cd "$PROJECT_DIR"
    if docker ps --filter name=smart-chatbot-db --format "{{.Names}}" | grep -q smart-chatbot-db; then
        echo "  PostgreSQL already running"
    else
        docker compose up -d postgres
        echo "  Waiting for PostgreSQL to be healthy..."
        for i in $(seq 1 30); do
            if docker ps --filter name=smart-chatbot-db --format "{{.Status}}" | grep -q healthy; then
                echo "  PostgreSQL healthy"
                break
            fi
            sleep 1
        done
    fi

    echo "[2/3] Starting Backend..."
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "  Backend already running (PID $(cat "$PID_FILE"))"
    else
        cd "$BACKEND_DIR"
        nohup "$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
        echo $! > "$PID_FILE"
        sleep 2
        if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "  Backend started (PID $(cat "$PID_FILE"))"
        else
            echo "  ERROR: Backend failed to start"
            tail -5 "$BACKEND_LOG"
            exit 1
        fi
    fi

    echo "[3/3] Checking Nginx..."
    if systemctl is-active --quiet nginx; then
        echo "  Nginx running"
    else
        echo "  WARNING: Nginx not running (start manually: systemctl start nginx)"
    fi

    echo ""
    echo ">>> All services started"
    echo "  Frontend : http://localhost"
    echo "  API      : http://localhost/api/health"
    echo "  DB       : localhost:5432"
}

stop() {
    echo ">>> Stopping SmartChatBot..."

    echo "[1/2] Stopping Backend..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
            for i in $(seq 1 10); do
                if ! kill -0 "$PID" 2>/dev/null; then
                    break
                fi
                sleep 0.5
            done
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null
            fi
            echo "  Backend stopped"
        else
            echo "  Backend not running"
        fi
        rm -f "$PID_FILE"
    else
        echo "  Backend not running"
    fi

    echo "[2/2] Stopping PostgreSQL..."
    cd "$PROJECT_DIR"
    if docker ps --filter name=smart-chatbot-db --format "{{.Names}}" | grep -q smart-chatbot-db; then
        docker compose down
        echo "  PostgreSQL stopped"
    else
        echo "  PostgreSQL not running"
    fi

    echo ">>> All services stopped"
}

status() {
    echo "=== Service Status ==="

    echo -n "PostgreSQL : "
    if docker ps --filter name=smart-chatbot-db --format "{{.Status}}" | grep -q healthy; then
        echo "RUNNING (healthy)"
    elif docker ps --filter name=smart-chatbot-db --format "{{.Status}}" | grep -q -v "^$"; then
        echo "RUNNING (not healthy)"
    elif docker ps -a --filter name=smart-chatbot-db --format "{{.Status}}" | grep -q Exited; then
        echo "STOPPED (exited)"
    else
        echo "NOT FOUND"
    fi

    echo -n "Backend   : "
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "RUNNING (PID $(cat "$PID_FILE"))"
    else
        echo "NOT RUNNING"
    fi

    echo -n "Nginx     : "
    if systemctl is-active --quiet nginx; then
        echo "RUNNING"
    else
        echo "NOT RUNNING"
    fi

    echo ""
    echo "=== Health Checks ==="

    echo -n "Frontend (port 80) : "
    if curl -sf -o /dev/null http://localhost/; then
        echo "OK"
    else
        echo "FAIL"
    fi

    echo -n "API (port 8000)    : "
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "OK"
    else
        echo "FAIL"
    fi

    echo -n "API via Nginx      : "
    if curl -sf http://localhost/api/health > /dev/null 2>&1; then
        echo "OK"
    else
        echo "FAIL"
    fi

    echo -n "PostgreSQL        : "
    if docker exec smart-chatbot-db pg_isready -U chat_admin -d smart_chatbot > /dev/null 2>&1; then
        echo "OK"
    else
        echo "FAIL"
    fi
}

restart() {
    stop
    echo ""
    start
}

case "${1:-status}" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)  status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
