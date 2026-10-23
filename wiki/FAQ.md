# Frequently Asked Questions

## What does the application do?

It collects and organizes AceStream channel references, creates M3U playlists, associates streams with TV channels, imports XMLTV EPG data, checks stream availability, and schedules recordings. It does not provide the underlying channel content.

## Which stream service does the current Docker image run?

The current entrypoint starts Outpace on `6878` and a separate checker on `6879`. It can also start the bundled AceStream search engine on `6880` (P2P `8625`). The search engine and Outpace have separate roles. Older documentation describing PyAcexy or a built-in Acestream engine on the main stream port is obsolete for this checkout.

## Do I need Docker?

Docker is recommended because it includes Outpace, ZeroNet, FFmpeg, and the other supporting binaries. A manual Python deployment may run the Flask app but does not automatically provide parity with all container services.

## Where is my data stored?

In Docker, the SQLite database and app configuration are under `/app/config`; recordings are under `/app/config/recordings`; ZeroNet data is under `/app/ZeroNet/data`. Keep these mounts and back them up when updating the container.

## How do I get a playlist?

Use `http://localhost:8040/playlist.m3u`. Add `?refresh=true` to request a source refresh or `?search=term` to filter channels. The generated stream URLs depend on the configured base URL and stream mode.

## Why are channels missing or offline?

Check that the source URL is enabled and its last scrape succeeded. Source pages can change or stop publishing references. Stream availability also depends on the upstream channel, peers, network connectivity, and a working backend. Use the channel check status and inspect the relevant service logs.

## How do I configure a TV guide or record a program?

Add an XMLTV source under EPG, refresh its data, map its guide channels to TV channels, then schedule a program from the guide. Recordings need a reachable stream and are written to `/app/config/recordings`.

## How do I enable Tor or WARP?

Set `ENABLE_TOR=true` for Tor. WARP requires `ENABLE_WARP=true`, a TUN device, network capabilities, and sysctls; see [Configuration](Configuration.md) and the provided Compose file. Do not grant those privileges unless needed.

## How do I find the API?

Open `http://localhost:8040/api/docs`. The health resource is `http://localhost:8040/api/health/`.

## Is it safe to expose the app publicly?

Do not expose the UI, API, ZeroNet UI, or streaming ports to an untrusted network without a deliberate access-control and reverse-proxy setup. The Flask app's forwarded-header handling is not a substitute for authentication.
