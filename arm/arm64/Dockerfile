# --- STAGE 0: Compilación de BoringTun Estable ---
FROM rust:1.85-slim AS builder
RUN apt-get update && apt-get install -y pkg-config libssl-dev curl ca-certificates tar && \
    mkdir -p /src && \
    curl -sSL https://github.com/cloudflare/boringtun/archive/refs/heads/master.tar.gz | tar -xz --strip-components=1 -C /src

WORKDIR /src

# Forzamos las versiones compatibles de 'time' en el archivo de configuración del proyecto
RUN sed -i 's/\[dependencies\]/\[dependencies\]\ntime = "=0.3.36"\ntime-core = "=0.1.2"/' boringtun-cli/Cargo.toml

RUN cargo install --path boringtun-cli

# --- STAGE 1: Descarga de Outpace desde GitHub usando la misma lógica Python ---
FROM python:3.10-slim AS builder-outpace
RUN apt-get update && apt-get install -y curl ca-certificates tar gzip unzip

RUN echo "import platform" > /tmp/download.py && \
    echo "import urllib.request" >> /tmp/download.py && \
    echo "import json" >> /tmp/download.py && \
    echo "import os" >> /tmp/download.py && \
    echo "import tarfile" >> /tmp/download.py && \
    echo "import zipfile" >> /tmp/download.py && \
    echo "import shutil" >> /tmp/download.py && \
    echo 'api_url = "https://api.github.com/repos/jamezrin/outpace/releases/latest"' >> /tmp/download.py && \
    echo 'headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Acestream-Scraper-Client"}' >> /tmp/download.py && \
    echo 'req = urllib.request.Request(api_url, headers=headers)' >> /tmp/download.py && \
    echo 'with urllib.request.urlopen(req) as response:' >> /tmp/download.py && \
    echo '    release_data = json.loads(response.read().decode())' >> /tmp/download.py && \
    echo 'assets = release_data.get("assets", [])' >> /tmp/download.py && \
    echo 'system = platform.system().lower()' >> /tmp/download.py && \
    echo 'machine = platform.machine().lower()' >> /tmp/download.py && \
    echo 'if machine in ["x86_64", "amd64"]:' >> /tmp/download.py && \
    echo '    arch_keywords = ["amd64", "x86_64", "x64"]' >> /tmp/download.py && \
    echo 'elif machine in ["aarch64", "armv8", "arm64"]:' >> /tmp/download.py && \
    echo '    arch_keywords = ["arm64", "aarch64"]' >> /tmp/download.py && \
	echo 'elif machine in ["arm", "hf", "armv7l"]:' >> /tmp/download.py && \
    echo '    arch_keywords = ["armv7", "armhf", "arm"]' >> /tmp/download.py && \
    echo 'else:' >> /tmp/download.py && \
    echo '    arch_keywords = [machine]' >> /tmp/download.py && \
    echo 'download_url = None' >> /tmp/download.py && \
    echo 'for asset in assets:' >> /tmp/download.py && \
    echo '    name = asset.get("name", "").lower()' >> /tmp/download.py && \
    echo '    if "linux" in name and any(ak in name for ak in arch_keywords):' >> /tmp/download.py && \
    echo '        if "apple" not in name and "windows" not in name:' >> /tmp/download.py && \
    echo '            download_url = asset.get("browser_download_url")' >> /tmp/download.py && \
    echo '            break' >> /tmp/download.py && \
    echo 'if not download_url and len(assets) == 1:' >> /tmp/download.py && \
    echo '    download_url = assets[0].get("browser_download_url")' >> /tmp/download.py && \
    echo 'print(f"Downloading Outpace asset from: {download_url}")' >> /tmp/download.py && \
    echo 'urllib.request.urlretrieve(download_url, "/tmp/outpace_asset")' >> /tmp/download.py && \
    echo 'target_path = "/usr/local/bin/outpace"' >> /tmp/download.py && \
    echo 'if download_url.endswith((".tar.gz", ".tgz")):' >> /tmp/download.py && \
    echo '    with tarfile.open("/tmp/outpace_asset", "r:gz") as tar:' >> /tmp/download.py && \
    echo '        member = next((m for m in tar.getmembers() if "outpace" in m.name and m.isfile()), None)' >> /tmp/download.py && \
    echo '        if not member:' >> /tmp/download.py && \
    echo '            member = next(m for m in tar.getmembers() if m.isfile())' >> /tmp/download.py && \
    echo '        extracted = tar.extractfile(member)' >> /tmp/download.py && \
    echo '        with open(target_path, "wb") as f_out:' >> /tmp/download.py && \
    echo '            f_out.write(extracted.read())' >> /tmp/download.py && \
    echo 'elif download_url.endswith(".zip"):' >> /tmp/download.py && \
    echo '    with zipfile.ZipFile("/tmp/outpace_asset", "r") as z:' >> /tmp/download.py && \
    echo '        fname = next((n for n in z.namelist() if "outpace" in n and not n.endswith("/")), z.namelist()[0])' >> /tmp/download.py && \
    echo '        with z.open(fname) as f_in, open(target_path, "wb") as f_out:' >> /tmp/download.py && \
    echo '            f_out.write(f_in.read())' >> /tmp/download.py && \
    echo 'else:' >> /tmp/download.py && \
    echo '    shutil.move("/tmp/outpace_asset", target_path)' >> /tmp/download.py && \
    echo 'os.chmod(target_path, 0o755)' >> /tmp/download.py

RUN python3 /tmp/download.py && rm /tmp/download.py

# --- STAGE 2: Base image con todas las dependencias ---
FROM --platform=linux/arm64 python:3.10-slim AS base

LABEL maintainer="visesa" \
      description="Acestream channel scraper with ZeroNet support" \
      version="2.1.1"

WORKDIR /app
RUN mkdir -p /app/config

# Copiamos el binario de BoringTun y preparamos el bridge
COPY --from=builder /usr/local/cargo/bin/boringtun-cli /usr/local/bin/boringtun-real
RUN echo -e '#!/bin/bash\n/usr/local/bin/boringtun-real --disable-drop-privileges "$@"' > /usr/local/bin/boringtun && \
    chmod +x /usr/local/bin/boringtun /usr/local/bin/boringtun-real

# Copiamos el binario de Outpace directamente desde la imagen oficial de ghcr.io/jamezrin/outpace
COPY --from=builder-outpace /usr/local/bin/outpace /usr/local/bin/outpace
RUN chmod +x /usr/local/bin/outpace

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
