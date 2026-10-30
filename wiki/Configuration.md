# Configuration Reference

## Where settings are stored

The first-run wizard initializes the application. Runtime application settings are managed in the web UI and stored in the SQLite database. In Docker, persistent state is under `/app/config`, including `/app/config/acestream.db`; the container also reads `/app/config/config.json` when present.

Important application settings:

| Setting | Default | Description |
|---|---:|---|
| `base_url` | empty | Base used to construct playlist stream URLs |
| `rescrape_interval` | 24 hours | Period for rescanning enabled source URLs |
| `checkstatus_interval` | 24 hours | Period for channel status checks |
| `checkstatus_enabled` | `true` | Enables automatic status checks unless overridden by the environment |
| `epg_refresh_interval` | 24 hours | Period for refreshing enabled EPG sources |
| `stream_mode` | `traditional` | `traditional` or `hls` |

Use the Configuration page to change these values. Add source URLs, TV channels, EPG mappings, and recording schedules through their respective pages.

## Image environment variables

These are the main environment variables defined or consumed by the current Docker image:

| Variable | Image default | Description |
|---|---:|---|
| `DOCKER_ENV` | `true` | Uses `/app/config` for config and database paths |
| `FLASK_PORT` | `8040` | Port used by Gunicorn |
| `TZ` | `Europe/Madrid` | Container timezone |
| `ENABLE_TOR` | `false` | Starts the Tor service |
| `ENABLE_WARP` | `false` | Runs WARP initialization |
| `ENABLE_ACESTREAM_SEARCH` | `true` | Starts the bundled search engine (`6880` HTTP, `8625` P2P) |
| `ENABLE_IPFS` | `false` | Starts Kubo IPFS with the lowpower profile |
| `CHECKSTATUS_ENABLED` | unset | When set, overrides the stored status-check setting |
| `WARP_LICENSE_KEY` | empty | Optional WARP license key |
| `WG_QUICK_USERSPACE_IMPLEMENTATION` | `boringtun` | WireGuard userspace implementation |
| `WG_THREADS` | `4` | WireGuard worker count |

The image also defines memory allocator variables (`LD_PRELOAD`, `MALLOC_CONF`). `entrypoint.sh` sets the Outpace bind addresses and tuning values internally; these are not presented as user-configurable application settings.

The current entrypoint starts Outpace on `6878` and a checker instance on `6879`, with peer ports `8621` and `8622`. When `ENABLE_IPFS=true`, Kubo stores its node data under `/app/config/ipfs` and runs with the lowpower profile, DHT client routing, a 512 KiB Bloom filter, two Go scheduler threads, and a 20–40 peer connection range. The bundled AceStream executable is used for search, not as the main Outpace stream service. Legacy variables and examples for PyAcexy are not part of the current startup configuration.

Sources may use native `ipfs://`/`ipns://` URIs or subdomain gateway URLs (`<CID>.ipfs.<gateway>` and `<name>.ipns.<gateway>`). Their original URL is stored, but content is fetched through Kubo's local gateway, so Kubo must be enabled with `ENABLE_IPFS=true`.

## Docker port reference

| Port | Service | Notes |
|---:|---|---|
| `8040` | Flask/Gunicorn | Configurable with `FLASK_PORT` |
| `1935` | Outpace RTMP listener | Internal service port |
| `6878` | Outpace stream listener | Main instance |
| `6879` | Outpace checker | Internal checker instance |
| `8621`, `8622` | Outpace peer listeners | Main and checker instances |
| `6880` | AceStream search HTTP API | Only when search is enabled |
| `8625` | AceStream search P2P | Only when search is enabled |
| `43110` | ZeroNet UI | Container ZeroNet service |
| `43111`, `26552` | ZeroNet peer ports | ZeroNet networking |

Ports must be explicitly published by Docker/Compose to be reachable from the host. See the repository's Compose file for its current mapping.

## Volumes

Mount the container directories rather than relying on data inside the image:

- `/app/config`: database and application configuration
- `/app/config/recordings`: recordings
- `/app/ZeroNet/data`: ZeroNet data

## ZeroNet

At startup, the entrypoint creates `/app/config/zeronet.conf` if it does not exist and links it into the ZeroNet installation. The default UI port is `43110`. Restrict access to the ZeroNet UI and configure allowed hosts according to your network.

## WARP and Tor

Tor is started by setting `ENABLE_TOR=true`.

For WARP, set `ENABLE_WARP=true` and provide the Linux tunnel device, `NET_ADMIN` and `SYS_ADMIN` capabilities, plus the network sysctls required by WireGuard. See the checked-in Compose configuration and `warp-setup.sh`. Do not enable these privileges unnecessarily.

## Reverse proxies and security

The Flask app uses `ProxyFix` for forwarded host/protocol/client headers. Only trust forwarded headers from a reverse proxy you control. Keep the UI/API private or place them behind a properly configured access-control layer; do not assume that publishing the container ports provides authentication.
