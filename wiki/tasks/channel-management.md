# TV Channel and Stream Management

TV channels are catalog entries that group stream entries broadcasting the same station. An AceStream channel is a stream reference; a TV channel is the user-facing station to which one or more stream references can be assigned.

## Typical workflow

1. Add or scrape AceStream entries from the Dashboard's channel list.
2. Create a TV channel on the TV Channels page, or generate one from existing stream entries.
3. Assign one or more stream entries to that TV channel.
4. Optionally associate an EPG identifier and review the guide on the EPG page.
5. Use the TV-channel detail view to inspect metadata, assigned streams, and availability.

Multiple stream references can be associated with one TV channel, allowing alternate sources. The recorder selects an online assigned stream when one is available.

## EPG association

Add and refresh an XMLTV source in EPG management. Match its guide-channel ID to the TV channel's EPG ID, manually or with the available matching operations. Stream entries can inherit EPG metadata from their TV-channel association; entries marked as protected from EPG updates are not overwritten by that synchronization.

## Recording

Schedule a program from the EPG interface. The background recording worker captures the selected program through the configured stream backend and FFmpeg. Files are stored in `/app/config/recordings` in Docker and may be split into parts and converted after capture.

Keep an adequate persistent volume mounted and monitor free disk space. Recording depends on a mapped EPG channel, a usable stream, and a working FFmpeg installation.

## API

TV-channel and recording API resources are documented in the interactive Swagger UI at `/api/docs`. Refer to that schema for current operations and payloads.
