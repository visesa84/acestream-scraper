# Acestream Scraper

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Docker](https://img.shields.io/badge/docker-supported-cyan.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Acestream Scraper is a Flask application for collecting and organizing AceStream channel references, managing TV channels and EPG data, and serving playlists or stream links to compatible players. It stores application data in SQLite and provides a web UI and a REST API.

It does not provide channel content. Configure sources or channel IDs that you are entitled to use.

## What it does

- Scrapes HTTP/HTTPS and ZeroNet sources for channel IDs and metadata.
- Lets you add and manage channels, search the catalog, filter out unwanted entries, and check stream availability.
- Supports a separate TV-channel catalog that can group multiple AceStream IDs for the same channel.
- Imports XMLTV EPG sources, maps guide entries to TV channels, and displays schedules.
- Generates M3U playlists and supports traditional and HLS stream modes.
- Schedules program recordings and processes recording files with FFmpeg.
- Exposes a Flask web interface and a REST API with Swagger documentation.
- Runs Outpace stream services in the Docker image; the bundled AceStream search engine can be enabled separately. ZeroNet, Tor, and Cloudflare WARP are included as optional supporting services/features.

## Run with Docker Compose

The repository includes a Compose configuration with persistent mounts for the database/configuration, recordings, and ZeroNet data:

1. **Create a docker-compose.yml file:**

```
version: '3.8'

services:
  acestream-scraper:
    image: visesa84/acestream-scraper-outpace:latest
    container_name: Acestream_Proxy
    cap_add:
      - NET_ADMIN
      - SYS_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1
      - net.ipv4.ip_forward=1
    environment:
      - TZ='Europe/Madrid'
      - ENABLE_TOR=false
      - WG_QUICK_USERSPACE_IMPLEMENTATION=boringtun
      - WG_THREADS=4
      - ENABLE_WARP=false
      - ENABLE_ACESTREAM_SEARCH=true
      - CONTAINER_NETWORK_MODE=host
      - WARP_LICENSE_KEY=
      - FLASK_PORT=8040
    ports:
      - "1935:1935"  # Outpace RTMP Port
      - "6878:6878"  # Outpace Port
      - "8040:8040"  # Flask application
      - "8621:8621"  # Outpace P2P Port
      - "8622:8622"  # Outpace P2P Port
      - "8625:8625"  # Acestream Search P2P Port
      - "43110:43110"  # ZeroNet UI
      - "43111:43111"  # ZeroNet peer
      - "26552:26552"  # ZeroNet peer
    volumes:
      - ./data/zeronet:/app/ZeroNet/data
      - ./data/config:/app/config
      - ./data/recordings:/app/config/recordings
    healthcheck:
      test: ["CMD", "/app/healthcheck.sh"]
      interval: 30s
      timeout: 10s
      retries: 3
```

2. **Start the service:**

   ```bash
   docker-compose up -d
   ```

Open `http://localhost:8040`. On first launch, follow the setup wizard, then add sources or channels.


The checked-in [docker-compose.yml](./docker-compose.yml) is the reference for the image tag, environment, port mappings, and volumes used by this checkout. Review it before exposing the service on a network. The main web port is `8040`; the Compose file also publishes the P2P, search-engine, and ZeroNet ports.

## Data and configuration

In the Docker image, `/app/config` is persistent application storage. It contains `acestream.db` and may contain `config.json`; recordings are stored in `/app/config/recordings`, and ZeroNet data is stored in `/app/ZeroNet/data`. Keep these mounts when replacing or updating a container.

Frequently used image environment variables:

| Variable | Image default | Purpose |
|---|---:|---|
| `FLASK_PORT` | `8040` | Web application port |
| `TZ` | `Europe/Madrid` | Container timezone |
| `ENABLE_TOR` | `false` | Start Tor for ZeroNet use |
| `ENABLE_WARP` | `false` | Initialize Cloudflare WARP; requires tunnel/network permissions |
| `ENABLE_ACESTREAM_SEARCH` | `true` | Start the bundled AceStream search service on port `6880` (P2P port `8625`) |
| `CHECKSTATUS_ENABLED` | application setting | Enable automatic stream checks |

Application settings such as the playlist base URL, rescrape/check intervals, EPG refresh interval, and stream mode can be managed in the web UI. See [Configuration](./wiki/Configuration.md).

## Web Interface

![image](https://github.com/visesa84/acestream-scraper-PyAcexy/blob/main/Dashboard.png)
![image](https://github.com/visesa84/acestream-scraper-PyAcexy/blob/main/Config.png)

## Web pages and endpoints

- Web UI: `/` (setup wizard on first run), `/dashboard` (channel catalog), `/search`, `/config`
- TV channels and schedules: `/tv-channels`, `/epg`, `/streams`, `/recordings`
- Playlist: `/playlist.m3u`; `?refresh=true` requests source refresh and `?search=term` filters the result
- Swagger API documentation: `/api/docs`
- Health API: `/api/health/`

## Runtime architecture

The image entrypoint starts the Flask/Gunicorn app, ZeroNet, and two Outpace processes (main stream listener on `6878` and a checker on `6879`). It can also start the AceStream search engine. The Outpace peer listeners use `8621` and `8622`; the search engine uses `8625`. Tor and WARP are optional.

Older documentation referred to PyAcexy and to a built-in Acestream engine serving the main stream port. Those instructions do not describe the current entrypoint: the current stream services are Outpace, while the bundled AceStream process is used for search.

## Development

The project uses Python, Flask, SQLAlchemy, and Flask-Migrate. Install the dependencies from `requirements.txt` and `requirements-prod.txt` as appropriate, then run the WSGI application with a compatible server. The Docker image is the supported way to run the full set of bundled services.

## Documentation

- [Wiki home](./wiki/Home.md)
- [Installation](./wiki/Installation.md)
- [Docker deployment](./wiki/Docker.md)
- [Usage](./wiki/Usage.md)
- [Configuration](./wiki/Configuration.md)
- [Requirements](./wiki/Requirements.md)
- [FAQ](./wiki/FAQ.md)
- [Bug reporting](./wiki/Bug-Reporting.md)
- [Contributing scraper data](./wiki/Contributing-Scraper-Data.md)

## Acknowledgements

This project uses Flask, SQLAlchemy, BeautifulSoup, Outpace, ZeroNet, FFmpeg, and other open-source software. See the dependency manifests and upstream projects for their respective licenses.

Special thanks to the developers of Flask, BeautifulSoup, SQLAlchemy, and other dependencies used in this project.
- [Acestream-scrapper](https://github.com/Pipepito/acestream-scraper) - Enhanced Acestream Scraper interface
- [Outpace](https://github.com/jamezrin/outpace) - AceStream reimplementation in Rust
