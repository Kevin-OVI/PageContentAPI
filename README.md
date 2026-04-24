# Page Content API (aiohttp + Selenium + ChromeDriver)

Page Content API loads a web page in headless Chrome and returns the extracted main content as markdown.

## Features

- `aiohttp` API with `GET /health` and `GET`/`POST /extract`
- Renders dynamic pages using Selenium + headless Chrome
- Converts extracted content to markdown (`main`/`article`/`role="main"` preferred)
- Optional extraction controls for links and media
- Configurable ChromeDriver pool for concurrent requests
- Automatic ChromeDriver download and cache in `.drivers/<version>/`

## Requirements

- Python 3.10+
- Google Chrome or Chromium installed locally
- Network access to Chrome for Testing metadata/download endpoints at startup

## Setup

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

The service reads these environment variables at import/startup:

- `HOST` (default: `0.0.0.0`)
- `PORT` (default: `8080`)
- `TIMEOUT_SECONDS` (default: `25`, minimum: `1`)
- `MAX_MARKDOWN_CHARS` (default: `100000`, minimum: `1`)
- `DRIVER_POOL_MIN_ACTIVE` (default: `1`, minimum: `0`)
- `DRIVER_POOL_MAX_ACTIVE` (default: `4`, minimum: `1`)
- `DRIVER_POOL_IDLE_TIMEOUT_SECONDS` (default: `120`, minimum: `0`)

Constraint:

- `DRIVER_POOL_MAX_ACTIVE >= DRIVER_POOL_MIN_ACTIVE`

## Run API

Default host/port (from env or defaults):

```cmd
python app.py
```

Override host/port from CLI:

```cmd
python app.py --host 127.0.0.1 --port 8080
```

On startup, the app resolves a platform-specific ChromeDriver (`win32`/`win64`/`mac-arm64`/`mac-x64`/`linux64`) and tries to match the locally installed Chrome version before falling back to the latest stable driver.

## API

### Health check

```cmd
curl http://127.0.0.1:8080/health
```

Response:

```json
{"status":"ok"}
```

### Extract content

Supported methods:

- `POST /extract` with JSON body
- `GET /extract` with query parameters

Parameters:

- `url` (required): `http`/`https` URL
- `include_links` (optional, default `true`): accepts booleans and values like `true/false`, `1/0`, `yes/no`, `on/off`
- `include_media` (optional, default `true`): same boolean parsing as above

POST example:

```cmd
curl -X POST http://127.0.0.1:8080/extract ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://example.com\",\"include_links\":true,\"include_media\":false}"
```

GET example:

```cmd
curl "http://127.0.0.1:8080/extract?url=https://example.com&include_links=false&include_media=true"
```

Success response (`200`):

```json
{
  "title": "Example Domain",
  "url": "https://example.com/",
  "markdown": "# Example Domain\n\n..."
}
```

Common error statuses:

- `400` invalid JSON, invalid URL, invalid boolean parameters, or local/private host blocked
- `502` ChromeDriver/Selenium failure
- `503` driver pool unavailable
- `504` page load timeout
- `500` unexpected error fallback

## Local Harness

Single request:

```cmd
python harness.py https://example.com
```

Concurrent run with extraction options:

```cmd
python harness.py https://example.com --concurrency 4 --count 10 --no-include-media
```

You can also target a non-default API base URL:

```cmd
python harness.py https://example.com --api-url http://127.0.0.1:8080
```

## Project Layout

- `app.py` - CLI entrypoint and server startup
- `harness.py` - local request runner/load helper
- `page_content_api/app_factory.py` - app wiring, startup, and cleanup hooks
- `page_content_api/routes/extract.py` - `/extract` request handling and validation
- `page_content_api/routes/health.py` - `/health` handler
- `page_content_api/browser/driver_setup.py` - driver resolution/download and WebDriver creation
- `page_content_api/browser/driver_pool.py` - pooled driver lifecycle and concurrency control
- `page_content_api/browser/extraction.py` - rendered page extraction flow
- `page_content_api/browser/markdown_processing.py` - HTML cleanup and markdown conversion
- `page_content_api/config.py` - constants and environment-backed settings
- `page_content_api/validation.py` - URL/host/boolean validation helpers

## Dependencies

From `requirements.txt`:

- `aiohttp`
- `selenium`
- `beautifulsoup4`
- `markdownify`
