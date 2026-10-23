# Installation Guide

## Recommended: Docker Compose

Install Docker Engine/Desktop and the Docker Compose plugin. From the project directory, start the checked-in configuration:

```powershell
docker compose up -d
docker compose ps
```

Open `http://localhost:8040` and complete the setup wizard. The repository Compose file already defines the current image, environment variables, port mappings, Linux network permissions, and persistent directories. Review it before deploying to a server, particularly before publishing ports outside your LAN.

Stop the deployment with:

```powershell
docker compose down
```

The Compose mounts preserve the database/configuration (`/app/config`), recordings (`/app/config/recordings`), and ZeroNet data (`/app/ZeroNet/data`). Do not remove those host directories when updating the container.

## Docker without Compose

The minimum web-app invocation is:

```powershell
docker run -d --name acestream-scraper `
  -p 8040:8040 `
  -v "${PWD}/config:/app/config" `
  -v "${PWD}/recordings:/app/config/recordings" `
  visesa84/acestream-scraper-pyacexy:latest
```

This minimal command does not publish the P2P, ZeroNet, or optional search ports and does not grant WARP's required network privileges. For the full port and permission setup, use the checked-in `docker-compose.yml`.

## Manual Python installation

Manual installation runs the Flask application and requires a compatible Python environment. It does not automatically install or start all the daemons and binaries bundled in the Docker image.

1. Install Python 3.10 or newer and FFmpeg if you need recording support.
2. Create and activate a virtual environment.
3. Install the dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pip install -r requirements-prod.txt
   ```

4. Start the WSGI application with a WSGI server, for example:

   ```powershell
   gunicorn --bind 127.0.0.1:8040 wsgi:app
   ```

The app creates its local `config` directory and SQLite database. Complete setup in the browser at `http://127.0.0.1:8040`. To use scraping, streaming, ZeroNet, status checks, or recordings, configure or install the corresponding external services; the Docker image's Outpace and ZeroNet processes are not started by this manual command.
