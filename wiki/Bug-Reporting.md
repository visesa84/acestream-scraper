# Bug Reporting Guide

Before reporting an issue:

1. Reproduce it on the version/image you are actually running.
2. Check the [FAQ](FAQ.md) and search existing project issues.
3. Collect logs and the exact configuration needed to reproduce the behavior.

## Include these details

- Image tag or source revision, deployment method, and host OS.
- Docker and Compose versions when applicable.
- The page or API endpoint involved, expected behavior, and actual behavior.
- Minimal steps to reproduce, frequency, and relevant screenshots.
- Which optional services are enabled (Tor, WARP, AceStream search) and which stream mode is selected.
- Relevant Compose settings with credentials, license keys, private URLs, and personal data removed.

Do not post passwords, tokens, WARP license keys, private source URLs, or complete database files. Redact public IPs and other identifying information where appropriate.

## Collect useful diagnostics

```powershell
docker compose ps
docker compose logs --tail 200 acestream-scraper
```

To see container health:

```powershell
docker inspect --format='{{json .State.Health}}' Acestream_Proxy
```

The application health resource is `http://localhost:8040/api/health/`. The container healthcheck is run by `/app/healthcheck.sh`; it is not the same route as the API resource.

The container writes service logs under `/app/logs`, including the application, Outpace, ZeroNet, migration, and optional AceStream search logs. Retrieve only the relevant log files and redact sensitive values before sharing.

## Report

Open an issue in the project tracker and provide the information above. Include a small sanitized example of the source structure if a scraper fails; do not include the real source URL unless you have permission to disclose it.
