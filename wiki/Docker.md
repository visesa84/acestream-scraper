# Docker Guide

Docker is the recommended deployment because the image bundles the Python application and supporting services (Outpace, ZeroNet, FFmpeg, and the optional search engine).

## Use this repository's Compose file

From the project directory:

```powershell
docker compose up -d
docker compose ps
docker compose logs -f acestream-scraper
```

Open `http://localhost:8040`. Stop the service with `docker compose down`. The checked-in [`docker-compose.yml`](../docker-compose.yml) is the authoritative example for this checkout. It mounts configuration, recordings, and ZeroNet data and publishes the configured application and P2P ports.

To update the image:

```powershell
docker compose pull
docker compose up -d
```

The Compose file uses a floating `latest` tag. For reproducible deployments, pin an image version that you have verified.

## Persistent data

Keep these container paths mounted to retain state when a container is replaced:

| Container path | Contents |
|---|---|
| `/app/config` | SQLite database (`acestream.db`) and application configuration |
| `/app/config/recordings` | Recording files |
| `/app/ZeroNet/data` | ZeroNet data |

Back up the mounted directories before upgrades or database maintenance.

## Services and ports

The current entrypoint runs the Flask/Gunicorn app on `FLASK_PORT` (default `8040`), Outpace on `6878` and `6879`, and ZeroNet. The Outpace peer listeners use `8621` and `8622`. When `ENABLE_ACESTREAM_SEARCH=true`, the bundled search engine uses HTTP port `6880` and P2P port `8625`. ZeroNet uses `43110` (UI), `43111`, and `26552`.

Publish only the ports needed for your deployment. The checked-in Compose file publishes `8040`, `8621`, `8622`, `8625`, `43110`, `43111`, and `26552`; it does not publish every port exposed or used internally by the image.

## Optional network features

- `ENABLE_TOR=true` starts Tor for deployments that use ZeroNet over Tor.
- `ENABLE_WARP=true` runs the WARP setup script. WARP requires `/dev/net/tun`, `NET_ADMIN`/`SYS_ADMIN` capabilities, and the relevant sysctls. The repository Compose file includes these permissions; only enable WARP when needed.

## Notes about older examples

Older wiki sections describe PyAcexy and a two-AceStream-engine startup script. Those are not started by the current `entrypoint.sh`. The current stream services are Outpace; the bundled AceStream executable is started for the search feature. Base your configuration on the checked-in [Dockerfile](../Dockerfile), [entrypoint](../entrypoint.sh), and Compose file rather than copied legacy examples.
