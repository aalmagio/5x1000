#!/bin/bash
# start.sh – avvia Gunicorn con uvicorn workers per FastAPI
#
# Uso:
#   chmod +x start.sh
#   ./start.sh            # avvio
#   ./start.sh stop       # stop
#   ./start.sh restart    # restart
#
# Il processo gira in background e scrive i log in logs/gunicorn.log
# Il PID viene salvato in logs/gunicorn.pid per stop/restart

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOG_DIR/gunicorn.pid"
LOG_FILE="$LOG_DIR/gunicorn.log"
BIND="127.0.0.1:8001"   # porta locale; nginx fa da proxy verso questo indirizzo
WORKERS=2               # 2 worker uvicorn sono più che sufficienti per dati statici

mkdir -p "$LOG_DIR"

# Attiva virtualenv se esiste (Plesk lo crea in percorsi variabili)
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
fi

case "${1:-start}" in
  start)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "Gunicorn è già in esecuzione (PID $(cat "$PID_FILE"))"
      exit 0
    fi
    echo "Avvio Gunicorn su $BIND..."
    cd "$SCRIPT_DIR"
    gunicorn main:app \
      --workers "$WORKERS" \
      --worker-class uvicorn.workers.UvicornWorker \
      --bind "$BIND" \
      --pid "$PID_FILE" \
      --log-file "$LOG_FILE" \
      --log-level info \
      --daemon
    echo "Gunicorn avviato (PID $(cat "$PID_FILE")). Log: $LOG_FILE"
    ;;

  stop)
    if [ -f "$PID_FILE" ]; then
      kill "$(cat "$PID_FILE")" && echo "Gunicorn fermato." || echo "Processo non trovato."
      rm -f "$PID_FILE"
    else
      echo "Nessun PID file trovato."
    fi
    ;;

  restart)
    $0 stop
    sleep 2
    $0 start
    ;;

  status)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "Running (PID $(cat "$PID_FILE"))"
    else
      echo "Stopped"
    fi
    ;;

  *)
    echo "Uso: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
