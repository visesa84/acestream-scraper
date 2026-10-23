#!/bin/bash
set -e

# Puerto por defecto de Flask si la variable no está definida
PORT=${FLASK_PORT:-5000}

# Consultar el endpoint correcto de la API utilizando -f para fallar ante errores HTTP (4xx, 5xx)
response=$(curl -s -f http://localhost:$PORT/api/health/)
if [ $? -ne 0 ]; then
    echo "Flask app healthcheck failed or endpoint unreachable"
    exit 1
fi

# Verificar si el estado devuelto por el JSON indica 'degraded'
if echo "$response" | grep -q '"status":"degraded"'; then
    echo "System health is degraded"
    exit 1
fi

# Todas las comprobaciones pasaron con éxito
echo "All health checks passed"
exit 0