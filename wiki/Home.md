# Acestream Scraper

## Overview

Acestream Scraper is a Flask web application for collecting AceStream channel references, organizing them into a channel catalog, and serving playlists and streams. It also includes TV-channel grouping, XMLTV EPG management, availability checks, and scheduled recordings.

The application manages references; it does not host channel content. You supply the source URLs or channel IDs and are responsible for using content lawfully.

## Current capabilities

- Scrape HTTP/HTTPS and ZeroNet pages.
- Search AceStream catalog results using the bundled search service.
- Manage channels, source URLs, blacklist entries, and stream status.
- Group multiple stream IDs under TV channels and associate EPG data.
- Generate M3U playlists in traditional or HLS mode.
- Schedule recordings from EPG programs; recordings are stored under `/app/config/recordings` in Docker.
- Use the REST API and interactive API docs at `/api/docs`.
- Optionally enable Tor and Cloudflare WARP.

The Docker image runs Outpace for stream handling. Do not rely on older instructions that describe PyAcexy as a service started by the current entrypoint.

## Wiki

- [Installation](Installation.md)
- [Docker deployment](Docker.md)
- [Usage](Usage.md)
- [Configuration](Configuration.md)
- [Requirements](Requirements.md)
- [FAQ](FAQ.md)
- [Bug reporting](Bug-Reporting.md)
- [Contributing scraper data](Contributing-Scraper-Data.md)
- [TV channel management](tasks/channel-management.md)

See the repository's [README](../README.md) and [Compose configuration](../docker-compose.yml) for the quickest deployment path and the actual ports and mounts used by this checkout.
