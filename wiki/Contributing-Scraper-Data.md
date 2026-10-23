# Contributing Scraper Data

The scraper supports HTTP/HTTPS and ZeroNet sources. If a source stops yielding channel data, sanitized structural details can help reproduce and fix the parser.

## Helpful information

- Source type: regular HTTP/HTTPS or ZeroNet.
- Whether the page contains data in its initial HTML, embedded JSON, or a separate API response.
- A short, redacted HTML/JSON sample showing the channel name and stream reference structure.
- The error/status shown by the application and the relevant sanitized log lines.
- Steps to reproduce, including whether the source requires authentication or JavaScript.

Remove credentials, session identifiers, tracking values, private addresses, and other identifying information. Do not share access tokens, passwords, or private URLs.

## Existing patterns

The HTTP scraper extracts channel references from page content and linked playlist/data formats. The ZeroNet scraper handles ZeroNet pages via the configured ZeroNet service. Actual parser behavior is defined in `app/scrapers/`; format support can change, so report what the current version accepts rather than assuming a pattern is supported.

## Report a scraper issue

Use the project issue tracker and include the sanitized sample and reproduction steps. Never submit channel data unless you have the right to disclose it.
