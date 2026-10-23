#!/bin/bash

# Create logs directory
LOG_DIR="/app/logs"
mkdir -p $LOG_DIR

# Configure log rotation - hourly rotation, keep 1 day of logs
cat > /etc/logrotate.d/acestream-services << EOF
$LOG_DIR/*.log {
    hourly
    rotate 7
    compress
    missingok
    notifempty
    create 0644 root root
}
EOF

echo "Starting cron daemon..."
cron || true

# Run logrotate once to ensure config is valid
logrotate /etc/logrotate.d/acestream-services --debug || true

# Preparamos las variables de control de procesos
OUTPACE_PID=""
OUTPACE_CHECK_STREAM_PID=""
ZERONET_PID=""
GUNICORN_PID=""
ACESTREAM_SEARCH_PID=""

# TRAP POSICIONADO AL PRINCIPIO: Asegura una salida limpia de TODOS los servicios
cleanup() {
    echo "Stopping all services cleanly..."
    # Matamos solo los PIDs que se hayan llegado a inicializar
    kill -TERM $GUNICORN_PID $ZERONET_PID $OUTPACE_PID $ACESTREAM_SEARCH_PID 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM EXIT

export ENABLE_WARP=${ENABLE_WARP:-false}

# Initialize WARP if enabled
if [ "${ENABLE_WARP}" = "true" ]; then
    echo "Initializing Cloudflare WARP..."
    /app/warp-setup.sh
fi

# Setup ZeroNet config if not exists
ZERONET_CONFIG="/app/config/zeronet.conf"
if [ ! -f "$ZERONET_CONFIG" ]; then
    echo "Creating default ZeroNet config..."
    cat > "$ZERONET_CONFIG" << EOF
[global]
ui_ip = *
ui_host =
 0.0.0.0
 localhost
ui_port = 43110
EOF
fi

# Create symlink to config
ln -sf "$ZERONET_CONFIG" /app/ZeroNet/zeronet.conf

# Start Tor if enabled
if [ "$ENABLE_TOR" = "true" ]; then
    echo "Starting Tor service..."
    service tor start >> "$LOG_DIR/tor.log" 2>&1
    # Add a brief pause to ensure Tor has time to start
    sleep 3
    echo "Tor service logs available at $LOG_DIR/tor.log"
fi

# --- Start Outpace ---
echo "Starting Outpace engine with experimental AceStream compatibility enabled..."
export OUTPACE_BIND=0.0.0.0:6878
export OUTPACE_RTMP_BIND=0.0.0.0:1935
export OUTPACE_PEER_LISTEN=0.0.0.0:8621
export OUTPACE_DATA_DIR=/root/.local/share/outpace
export OUTPACE_EXPERIMENTAL_ACE_COMPAT=1
export OUTPACE_MAX_ACTIVE_UPSTREAMS=6
export OUTPACE_MAX_PARALLEL_CONNECT=16
export OUTPACE_REQUEST_TIMEOUT_MS=3500
export OUTPACE_CONNECT_TIMEOUT_MS=5000
export OUTPACE_READ_TIMEOUT_MS=10000
export OUTPACE_CACHE_SIZE_MB=128
export OUTPACE_MAX_CONNECTIONS_PER_STREAM=35

outpace serve >> "$LOG_DIR/outpace.log" 2>&1 &
OUTPACE_PID=$!

sleep 3
echo "Outpace check stream engine startup log: $LOG_DIR/outpace_check_stream.log"

# --- Start Outpace Check Stream Engine ---
echo "Starting Outpace check stream engine..."
export OUTPACE_BIND=0.0.0.0:6879
unset OUTPACE_RTMP_BIND
export OUTPACE_PEER_LISTEN=0.0.0.0:8622
export OUTPACE_DATA_DIR=/root/.local/share/outpace_check
export OUTPACE_EXPERIMENTAL_ACE_COMPAT=1
export OUTPACE_MAX_ACTIVE_UPSTREAMS=4
export OUTPACE_MAX_PARALLEL_CONNECT=8
export OUTPACE_REQUEST_TIMEOUT_MS=3500
export OUTPACE_CONNECT_TIMEOUT_MS=5000
export OUTPACE_READ_TIMEOUT_MS=10000
export OUTPACE_CACHE_SIZE_MB=32

outpace serve >> "$LOG_DIR/outpace_check_stream.log" 2>&1 &
OUTPACE_CHECK_STREAM_PID=$!

sleep 3
echo "Outpace engine startup log: $LOG_DIR/outpace.log"

export ENABLE_ACESTREAM_SEARCH=${ENABLE_ACESTREAM_SEARCH:-false}

if [ "$ENABLE_ACESTREAM_SEARCH" = "true" ]; then
	/opt/acestream/start-engine --client-console --http-port 6880 --port 8625 >> "$LOG_DIR/acestream.log" 2>&1 & 
	ACESTREAM_SEARCH_PID=$!	

	sleep 3
	echo "Acestream engine startup log: $LOG_DIR/acestream.log"
fi

# Start ZeroNet in the background
cd /app/ZeroNet
echo "Starting ZeroNet..."
python3 zeronet.py main >> "$LOG_DIR/zeronet.log" 2>&1 &
ZERONET_PID=$!
echo "ZeroNet logs available at $LOG_DIR/zeronet.log"

# Wait for ZeroNet to start
echo "Waiting for ZeroNet to initialize..."
sleep 10

# Run database migrations before starting the app
cd /app
echo "Running database migrations..."
python manage.py upgrade >> "$LOG_DIR/migrations.log" 2>&1
if [ $? -ne 0 ]; then
    echo "WARNING: Database migration failed — check $LOG_DIR/migrations.log"
else
    echo "Database migrations completed successfully."
fi

# Start Flask app with Gunicorn
echo "Starting Flask application on port $FLASK_PORT..."
gunicorn --bind "0.0.0.0:$FLASK_PORT" \
    --workers 4 \
    --threads 4 \
    --worker-class gthread \
    --timeout 300 \
    --keep-alive 5 \
    --log-level info \
    --forwarded-allow-ips="*" \
    "wsgi:app" &
GUNICORN_PID=$!

echo "Services started. Monitoring processes..."

# Mantenemos el contenedor vivo monitorizando gunicorn
wait $GUNICORN_PID