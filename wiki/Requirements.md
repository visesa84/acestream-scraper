# Requirements

## Docker deployment

The recommended deployment requires Docker Engine or Docker Desktop with the Docker Compose plugin. The repository image targets Linux containers. Windows users can run it through Docker Desktop with Linux containers enabled.

For the optional Cloudflare WARP tunnel, the container needs access to `/dev/net/tun`, `NET_ADMIN` and `SYS_ADMIN` capabilities, and the configured network sysctls. The provided Compose file shows these settings.

## Manual deployment

- Python 3.10 or newer
- Dependencies from `requirements.txt` and `requirements-prod.txt`
- A WSGI server (the container uses Gunicorn)
- FFmpeg for recording capture and processing
- External stream/ZeroNet services if you need features provided by the bundled Docker processes

The manual app does not start Outpace, ZeroNet, Tor, or the bundled AceStream search engine automatically.

## Network ports

Publish only the ports your deployment needs:

| Port | Service | When needed |
|---:|---|---|
| `8040` | Flask web UI/API | Always |
| `6878`, `6879` | Outpace main/checker HTTP listeners | Stream handling and checks |
| `8621`, `8622` | Outpace peer listeners | P2P streaming |
| `6880`, `8625` | AceStream search HTTP/P2P | When `ENABLE_ACESTREAM_SEARCH=true` |
| `43110` | ZeroNet UI | ZeroNet |
| `43111`, `26552` | ZeroNet peers | ZeroNet networking |
| `1935` | Outpace RTMP | Only if using RTMP |

The current Compose file publishes a subset of these ports. Check that file before making any port reachable outside your trusted network.

## Persistent storage

Mount and back up `/app/config`, `/app/config/recordings`, and `/app/ZeroNet/data`. Space usage depends on the database, ZeroNet activity, and the size and duration of recordings.

## Network access

Scraping requires access to the configured sources. Stream checks and playback require a reachable backend and network access to the relevant peers. EPG refresh needs outbound access to configured XMLTV URLs.
