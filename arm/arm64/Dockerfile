# --- STAGE 0: Compilación de BoringTun Estable ---
FROM rust:1.85-slim AS builder
RUN apt-get update && apt-get install -y pkg-config libssl-dev curl ca-certificates tar && \
    mkdir -p /src && \
    curl -sSL https://github.com/cloudflare/boringtun/archive/refs/heads/master.tar.gz | tar -xz --strip-components=1 -C /src

WORKDIR /src

# Forzamos las versiones compatibles de 'time' en el archivo de configuración del proyecto
RUN sed -i 's/\[dependencies\]/\[dependencies\]\ntime = "=0.3.36"\ntime-core = "=0.1.2"/' boringtun-cli/Cargo.toml

RUN cargo install --path boringtun-cli

# --- STAGE 1: Descarga de Outpace desde GitHub ---
FROM --platform=linux/arm64 python:3.10-slim AS builder-outpace
RUN apt-get update && apt-get install -y curl ca-certificates tar gzip unzip jq

COPY outpace_fix/ /tmp/outpace_fix/
RUN mkdir -p /tmp/licenses_outpace

RUN set -eu; \
    release="$(curl -fsSL -H 'Accept: application/vnd.github+json' -H 'User-Agent: Acestream-Scraper-Client' https://api.github.com/repos/jamezrin/outpace-stream/releases/latest)"; \
    tag="$(printf '%s' "$release" | jq -er '.tag_name')"; \
    target_arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    \
    # Mapeo corregido aarch64 para coincidir con la nomenclatura real de GitHub
    case "$target_arch" in \
        amd64|x86_64) kw="x86_64" ;; \
        arm64|aarch64) kw="aarch64" ;; \
        arm|armv7|armv7l) kw="armv7" ;; \
        *) kw="$target_arch" ;; \
    esac; \
    \
    echo "Buscando asset para la arquitectura clave: $kw"; \
    \
    # Selección compatible con jq estándar utilizando contains en lugar de endsWith
    download_url="$(printf '%s' "$release" | jq -r --arg kw "$kw" \
        '.assets[]? | select((.name | contains($kw)) and (.name | contains("linux")) and (.name | contains(".tar.gz"))) | .browser_download_url' | head -n 1)"; \
    \
    if [ -z "$download_url" ] || [ "$download_url" = "null" ]; then \
        echo "Error: No se encontró el asset de Linux compatible con $kw."; \
        exit 1; \
    fi; \
    \
    echo "Descargando Outpace asset desde: $download_url"; \
    curl -fsSL "$download_url" -o /tmp/outpace_asset; \
    mkdir -p /tmp/outpace_extracted; \
    \
    target_path="/usr/local/bin/outpace"; \
    case "$download_url" in \
        *.tar.gz|*.tgz) \
            tar -xzf /tmp/outpace_asset -C /tmp/outpace_extracted; \
            extracted_file=$(find /tmp/outpace_extracted -type f ! -name "*.md" ! -iname "*license*" ! -iname "*copying*" | grep -iE "outpace" | head -n 1); \
            [ -z "$extracted_file" ] && extracted_file=$(find /tmp/outpace_extracted -type f | head -n 1); \
            cp "$extracted_file" "$target_path"; \
            license_file=$(find /tmp/outpace_extracted -type f -iname "*license*" -o -iname "*copying*" | head -n 1); \
            if [ -n "$license_file" ]; then \
                cp "$license_file" /tmp/licenses_outpace/LICENSE-outpace; \
            fi; \
            ;; \
        *.zip) \
            python3 -c "import zipfile; z = zipfile.ZipFile('/tmp/outpace_asset'); z.extractall('/tmp/outpace_extracted')"; \
            extracted_file=$(find /tmp/outpace_extracted -type f ! -name "*.md" ! -iname "*license*" ! -iname "*copying*" | grep -iE "outpace" | head -n 1); \
            [ -z "$extracted_file" ] && extracted_file=$(find /tmp/outpace_extracted -type f | head -n 1); \
            cp "$extracted_file" "$target_path"; \
            license_file=$(find /tmp/outpace_extracted -type f -iname "*license*" -o -iname "*copying*" | head -n 1); \
            if [ -n "$license_file" ]; then \
                cp "$license_file" /tmp/licenses_outpace/LICENSE-outpace; \
            fi; \
            ;; \
        *) \
            mv /tmp/outpace_asset "$target_path"; \
            ;; \
    esac; \
    chmod +x "$target_path"

# --- STAGE 2: Descarga del binario precompilado de Kubo desde GitHub ---
FROM builder-outpace AS builder-kubo
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl jq ca-certificates && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /tmp/licenses_kubo
RUN set -eu; \
    release="$(curl -fsSL -H 'Accept: application/vnd.github+json' -H 'User-Agent: Acestream-Scraper-Client' https://api.github.com/repos/ipfs/kubo/releases/latest)"; \
    tag="$(printf '%s' "$release" | jq -er '.tag_name')"; \
    target_arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "$target_arch" in \
        amd64|arm64) \
            asset_name="kubo_${tag}_linux-${target_arch}.tar.gz"; \
            download_url="$(printf '%s' "$release" | jq -er --arg name "$asset_name" '.assets[] | select(.name == $name) | .browser_download_url')"; \
            curl -fsSL "$download_url" -o /tmp/kubo.tar.gz; \
            tar -xzf /tmp/kubo.tar.gz -C /tmp kubo/ipfs kubo/LICENSE kubo/LICENSE-APACHE kubo/LICENSE-MIT; \
            install -m 755 /tmp/kubo/ipfs /usr/local/bin/ipfs; \
            cp /tmp/kubo/LICENSE* /tmp/licenses_kubo/; \
            ;; \
        *) \
            exit 1; \
            ;; \
    esac

# --- STAGE 3: Base image con todas las dependencias ---
FROM --platform=linux/arm64 python:3.10-slim AS base

LABEL maintainer="visesa" \
      description="Acestream channel scraper with ZeroNet support" \
      version="2.3.1"

WORKDIR /app
RUN mkdir -p /app/config

# Copiamos el binario de BoringTun y preparamos el bridge
COPY --from=builder /usr/local/cargo/bin/boringtun-cli /usr/local/bin/boringtun-real
RUN echo -e '#!/bin/bash\n/usr/local/bin/boringtun-real --disable-drop-privileges "$@"' > /usr/local/bin/boringtun && \
    chmod +x /usr/local/bin/boringtun /usr/local/bin/boringtun-real

# Copiamos el binario de Outpace directamente desde la imagen oficial de ghcr.io/jamezrin/outpace
COPY --from=builder-outpace /usr/local/bin/outpace /usr/local/bin/outpace
RUN chmod +x /usr/local/bin/outpace

# Copiamos el binario de Kubo descargado para la arquitectura de la imagen
COPY --from=builder-kubo /usr/local/bin/ipfs /usr/local/bin/ipfs

# Instalar dependencias del sistema + herramientas de WireGuard
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg gcc python3-dev build-essential \
    tor ca-certificates \
    wireguard-tools iproute2 ffmpeg openresolv unzip binutils \
    libssl-dev libffi-dev logrotate cron \
    libsecp256k1-dev libtool autoconf automake pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Configuración de TOR
RUN echo "ControlPort 9051" >> /etc/tor/torrc && \
    echo "CookieAuthentication 1" >> /etc/tor/torrc

# 1. Instalar librerías de Python
RUN pip install --no-cache-dir \
    "msgpack-python" "gevent==22.10.2" "PySocks" "gevent-websocket" \
    "python-bitcoinlib" "bencode.py" "merkletools" "pysha3" \
    "cgi-tools" "urllib3<2.0.0" "rich" "pyaes" \
    "coincurve" "base58" "defusedxml" "rsa" "psutil"

# Descargar e instalar ZeroNet
RUN mkdir -p ZeroNet && \
    wget https://github.com/zeronet-conservancy/zeronet-conservancy/archive/refs/heads/master.tar.gz -O ZeroNet.tar.gz && \
    tar xvf ZeroNet.tar.gz && \
    mv zeronet-conservancy-master/* ZeroNet/ && \
    rm -rf ZeroNet.tar.gz zeronet-conservancy-master

# --- ETAPA FINAL ---
# Usamos la base que acabamos de construir para mantener las dependencias
FROM base
WORKDIR /app
RUN mkdir -p /licenses
COPY LICENSE /licenses/LICENSE-acestream-scraper
COPY --from=builder-outpace /tmp/licenses_outpace/ /licenses/
COPY --from=builder-kubo /tmp/licenses_kubo/ /licenses/

# 1. Mover las dependencias ARRIBA para aprovechar la caché de Docker
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-prod.txt

# 2. Copiar archivos comunes de la aplicación
COPY migrations/ ./migrations/
COPY migrations_app.py manage.py wsgi.py ./
COPY app/ ./app/

# 3. Copiar scripts específicos.
COPY --chmod=0755 arm/arm64/entrypoint.sh ./
COPY --chmod=0755 healthcheck.sh warp-setup.sh ./
COPY --chmod=0755 arm/arm64/wgcf /usr/local/bin/wgcf

# Variables de entorno Acestream
ENV DOCKER_ENV=true
ENV TZ='Europe/Madrid'
ENV ENABLE_TOR=false
ENV WG_QUICK_USERSPACE_IMPLEMENTATION=boringtun
ENV WG_THREADS=4
ENV ENABLE_WARP=false
ENV ENABLE_IPFS=true
ENV CONTAINER_NETWORK_MODE=host
ENV WARP_LICENSE_KEY=
ENV FLASK_PORT=8040
	
# Puertos, Volúmenes y Salud
EXPOSE 1935
EXPOSE 8040
EXPOSE 43110
EXPOSE 43111
EXPOSE 26552
EXPOSE 6878
EXPOSE 8621
EXPOSE 8622
EXPOSE 8625
VOLUME ["/app/ZeroNet/data", "/app/config", "/app/config/recordings"]

RUN chmod -R 755 /app
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s CMD /app/healthcheck.sh

ENTRYPOINT ["/app/entrypoint.sh"]
