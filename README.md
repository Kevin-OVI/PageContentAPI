# Page Content API (aiohttp + ChromeDriver)

This project exposes an HTTP API that loads web pages with ChromeDriver and returns extracted page content in markdown.

## Features

- `aiohttp` API with `/extract` endpoint
- Downloads the latest stable ChromeDriver at startup
- Uses headless Chrome via Selenium to render dynamic pages
- Converts main page content to markdown

## Requirements

- Python 3.10+
- Google Chrome installed
- Windows (current implementation downloads `chromedriver.exe`)

## Setup

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run API

```cmd
python app.py
```

`app.py` is now a thin entrypoint. Core logic lives in the `page_content_api/` package:

- `page_content_api/app_factory.py` - app wiring, startup, cleanup
- `page_content_api/handlers.py` - HTTP handlers for `/health` and `/extract`
- `page_content_api/driver_setup.py` - ChromeDriver download and browser setup
- `page_content_api/extraction.py` - rendered page extraction flow
- `page_content_api/markdown_processing.py` - HTML-to-markdown conversion
- `page_content_api/validation.py` - input parsing and host validation helpers
- `page_content_api/config.py` - shared constants

On startup, the service downloads and caches the latest stable ChromeDriver under `.drivers/<version>/chromedriver.exe`.

## API Usage

### Health check

```cmd
curl http://127.0.0.1:8080/health
```

### Extract markdown

```cmd
curl -X POST http://127.0.0.1:8080/extract ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://example.com\"}"
```

You can also use a query string:

```cmd
curl "http://127.0.0.1:8080/extract?url=https://example.com"
```

## Local Harness

```cmd
python harness.py https://example.com
```

This prints status, title, final URL, and a markdown preview.

## Notes

- The API blocks local/private hosts to reduce SSRF risk.
- Long pages are truncated to keep payloads bounded.
- If page load times out, API returns `504`.


