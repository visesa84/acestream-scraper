# --- STAGE 0: Compilación de BoringTun Estable ---
FROM rust:1.85-slim AS builder-boringtun
RUN apt-get update && apt-get install -y pkg-config libssl-dev curl ca-certificates tar && \
    mkdir -p /src && \
    curl -sSL https://github.com/cloudflare/boringtun/archive/refs/heads/master.tar.gz | tar -xz --strip-components=1 -C /src

WORKDIR /src
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
    echo 'elif machine in ["aarch64", "armv8"]:' >> /tmp/download.py && \
    echo '    arch_keywords = ["arm64", "aarch64"]' >> /tmp/download.py && \
	echo 'elif machine in ["arm", "hf", "armv7l"]:' >> /tmp/download.py && \
    echo '    arch_keywords = ["armv7", "armhf", "arm"]' >> /tmp/download.py && \
    echo 'else:' >> /tmp/download.py && \
    echo '    arch_keywords = [machine]' >> /tmp/download.py && \
    echo 'download_url = None' >> /tmp/download.py && \
    echo 'for asset in assets:' >> /tmp/download.py && \
    echo '    name = asset.get("name", "").lower()' >> /tmp/download.py && \
    echo '    if (system in name or "linux" in name) and any(ak in name for ak in arch_keywords):' >> /tmp/download.py && \
    echo '        download_url = asset.get("browser_download_url")' >> /tmp/download.py && \
    echo '        break' >> /tmp/download.py && \
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

# --- STAGE 2: Imagen Base con Dependencias y Binarios ---
FROM python:3.10-slim AS base

LABEL maintainer="visesa" \
      description="Acestream channel scraper with Outpace and ZeroNet support" \
      version="2.0.0"

WORKDIR /app
RUN mkdir -p /app/config

# Copiamos y configuramos el binario de BoringTun
COPY --from=builder-boringtun /usr/local/cargo/bin/boringtun-cli /usr/local/bin/boringtun
RUN chmod +x /usr/local/bin/boringtun && \
    mv /usr/local/bin/boringtun /usr/local/bin/boringtun-real

RUN echo '#!/bin/bash\n/usr/local/bin/boringtun-real --disable-drop-privileges "$@"' > /usr/local/bin/boringtun && \
    chmod +x /usr/local/bin/boringtun

# Copiamos el binario de Outpace descargado desde GitHub
COPY --from=builder-outpace /usr/local/bin/outpace /usr/local/bin/outpace
RUN chmod +x /usr/local/bin/outpace

# Instalar dependencias del sistema necesarias (incluyendo ffmpeg para procesamiento de streams/HLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg gcc python3-dev build-essential \
    tor git lsb-release apt-transport-https ca-certificates \
    wireguard-tools iproute2 \
    openresolv logrotate cron ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Configuración de TOR
RUN echo "ControlPort 9051" >> /etc/tor/torrc && \
    echo "CookieAuthentication 1" >> /etc/tor/torrc

# Dependencias de Python esenciales
RUN pip install --no-cache-dir \
    "msgpack-python" \
    "gevent==22.10.2" \
    "PySocks" \
    "gevent-websocket" \
    "python-bitcoinlib" \
    "bencode.py" \
    "merkletools" \
    "pysha3" \
    "cgi-tools" \
    "urllib3<2.0.0" \
    "rich" \
    "requests" \
    "pyaes" \
    "coincurve" \
    "base58" \
    "defusedxml" \
    "rsa" \
    "psutil"

# Descargar e instalar ZeroNet
RUN mkdir -p ZeroNet && \
    wget https://github.com/zeronet-conservancy/zeronet-conservancy/archive/refs/heads/master.tar.gz -O ZeroNet.tar.gz && \
    tar xvf ZeroNet.tar.gz && \
    mv zeronet-conservancy-master/* ZeroNet/ && \
    rm -rf ZeroNet.tar.gz zeronet-conservancy-master

# Install Acestream Engine
ENV ACESTREAM_VERSION="3.2.11_ubuntu_22.04_x86_64_py3.10"
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install acestream dependencies
RUN apt-get update \
  && apt-get install --no-install-recommends -y \
      ca-certificates wget sudo \
      python3-gi \
      gir1.2-gtk-3.0 \
      ffmpeg \
  && rm -rf /var/lib/apt/lists/* \
  #
  # Download acestream
  && wget --progress=dot:giga "https://download.acestream.media/linux/acestream_${ACESTREAM_VERSION}.tar.gz" \
  && mkdir acestream \
  && tar zxf "acestream_${ACESTREAM_VERSION}.tar.gz" -C acestream \
  && rm "acestream_${ACESTREAM_VERSION}.tar.gz" \
  && mv acestream /opt/acestream \
  && pushd /opt/acestream || exit \
  && bash ./install_dependencies.sh \
  && popd || exit

RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Variables de entorno predeterminadas
ENV DOCKER_ENV=true
ENV TZ='Europe/Madrid'
ENV ENABLE_TOR=false
ENV WG_QUICK_USERSPACE_IMPLEMENTATION=boringtun
ENV WG_THREADS=4
ENV ENABLE_WARP=false
ENV ENABLE_ACESTREAM_SEARCH=true
ENV CONTAINER_NETWORK_MODE=host
ENV WARP_LICENSE_KEY=
ENV FLASK_PORT=8040

# --- STAGE 3: Imagen Final de la Aplicación ---
FROM base

LABEL description="Acestream channel scraper with Outpace and ZeroNet support" \
      version="2.0.0"

# Copiar archivos de la aplicación y scripts de control
COPY --chmod=0755 entrypoint.sh /app/entrypoint.sh
COPY --chmod=0755 healthcheck.sh /app/healthcheck.sh
COPY --chmod=0755 warp-setup.sh /app/warp-setup.sh
COPY --chmod=0755 wgcf /usr/local/bin/wgcf
COPY requirements.txt requirements-prod.txt ./
COPY migrations/ ./migrations/
COPY migrations_app.py manage.py ./
COPY wsgi.py ./
COPY app/ ./app/

RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh /app/warp-setup.sh /usr/local/bin/wgcf

# Instalar dependencias de Python del proyecto
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-prod.txt

# Exponer puertos de la app web, ZeroNet y Outpace
EXPOSE 1935
EXPOSE 8040
EXPOSE 43110
EXPOSE 43111
EXPOSE 26552
EXPOSE 6878
EXPOSE 8621
EXPOSE 8622
EXPOSE 8625

VOLUME ["/app/ZeroNet/data"]
VOLUME ["/app/config"]
VOLUME ["/app/config/recordings"]

WORKDIR /app
RUN chmod -R 755 /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD /app/healthcheck.sh

ENTRYPOINT ["/app/entrypoint.sh"]