# Usage Guide

## Open the application

Start the Docker deployment and visit `http://localhost:8040`. On a new installation, complete the setup wizard before using the dashboard. The main pages are Dashboard, Channels, Search, Configuration, TV Channels, EPG, Streams, and Recordings.

## Add and refresh sources

In Configuration, add a source URL and choose its type:

- **Regular** for HTTP/HTTPS pages.
- **ZeroNet** for ZeroNet content; the container's ZeroNet service listens on port `43110`.

Use the source list to enable/disable a source, refresh it, or remove it. The scraper updates the channel catalog from the results. Manual channel entries are managed separately and are not scraped as pages.

## Manage channels

Use the channel list on the Dashboard to add, edit, search, check, enable/disable, or delete AceStream entries. Search can also query the bundled AceStream search service when that service is enabled. Channel checks depend on a reachable stream backend and may take time.

The blacklist lets you exclude matches from scraped results. A TV channel is a separate grouping entity: assign one or more stream IDs to it so the UI and EPG can treat them as alternate streams for the same station. See [TV channel management](tasks/channel-management.md).

## EPG, streams, and recordings

1. Add an XMLTV-compatible EPG URL in EPG management.
2. Fetch the guide and map EPG channel IDs to TV channels (manually or using the available matching tools).
3. Review schedules and choose a program to schedule or cancel a recording.
4. Use Recordings to view scheduled/active jobs and completed files.

Recordings are written beneath `/app/config/recordings` in the Docker image. FFmpeg is used to capture streams and process completed recording parts.

The Streams page provides stream management/status information. The application supports `traditional` and `hls` stream modes; select the mode in Configuration.

## M3U playlists

The playlist endpoint is:

```text
http://localhost:8040/playlist.m3u
```

Supported query options:

- Force a source refresh: `?refresh=true`
- Filter by channel name: `?search=sports`
- Set a playlist base URL for that response: `?base_url=http%3A%2F%2Fhost%2Fstream%3Fid%3D`

Add the URL as a network playlist in a compatible player. The output stream URLs depend on the configured base URL and stream mode. The application does not relay or guarantee that the source stream is available.

## REST API

Swagger documentation is available at `/api/docs`. The API includes resources for channels, source URLs, playlists, statistics, health, configuration, AceStream search, EPG, TV channels, recordings, blacklist entries, active streams, WARP, and users. Consult the interactive schema for current request and response formats.

The health resource is `/api/health/`. The Docker healthcheck script is separate; use `docker inspect`/`docker compose ps` to see the container health state.

## Network exposure

Keep the UI and API on a trusted network or behind an appropriately configured authentication-enabled reverse proxy. Do not expose ZeroNet's UI or the streaming ports publicly unless you understand the access controls and network implications.
