import json
import logging
import time
from urllib.parse import urlparse

from aiohttp import web
from selenium.common import TimeoutException, WebDriverException
from selenium.webdriver.chrome.webdriver import WebDriver

from ..browser import DriverPool, extract_markdown_with_tab
from ..config import MAX_MARKDOWN_CHARS, TIMEOUT_SECONDS
from ..validation import is_http_url, looks_local_host, parse_bool_param

LOGGER = logging.getLogger(__name__)


async def handle_extract(request: web.Request) -> web.Response:
    LOGGER.info("Received extract request method=%s path=%s", request.method, request.path)
    if request.method == "POST":
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            LOGGER.warning("Rejecting extract request: invalid JSON body")
            return web.json_response({"error": "Invalid JSON body."}, status=400)
        url = str(payload.get("url", "")).strip()
        include_links_raw = payload.get("include_links")
        include_media_raw = payload.get("include_media")
    else:
        url = request.query.get("url", "").strip()
        include_links_raw = request.query.get("include_links")
        include_media_raw = request.query.get("include_media")

    try:
        include_links = parse_bool_param(include_links_raw, default=True)
        include_media = parse_bool_param(include_media_raw, default=True)
    except ValueError:
        LOGGER.warning("Rejecting extract request: invalid include_links/include_media")
        return web.json_response(
            {"error": "include_links/include_media must be boolean values."},
            status=400,
        )

    if not is_http_url(url):
        LOGGER.warning("Rejecting extract request: invalid URL format")
        return web.json_response(
            {"error": "Provide a valid HTTP/HTTPS URL via query or JSON body."},
            status=400,
        )

    hostname = urlparse(url).hostname or ""
    if looks_local_host(hostname):
        LOGGER.warning("Rejecting extract request: local/private hostname=%s", hostname)
        return web.json_response(
            {"error": "Local/private hosts are not allowed."},
            status=400,
        )

    driver_pool: DriverPool = request.app["driver_pool"]
    acquire_started = time.monotonic()

    def use_driver(driver: WebDriver):
        pool_wait_ms = int((time.monotonic() - acquire_started) * 1000)
        LOGGER.info("Driver acquired for hostname=%s wait_ms=%d", hostname, pool_wait_ms)

        extraction_started = time.monotonic()
        result = extract_markdown_with_tab(driver, url, TIMEOUT_SECONDS, MAX_MARKDOWN_CHARS, include_links, include_media)
        extraction_ms = int((time.monotonic() - extraction_started) * 1000)

        LOGGER.info(
            "Request succeeded for hostname=%s extract_ms=%d total_ms=%d",
            hostname,
            extraction_ms,
            int((time.monotonic() - acquire_started) * 1000),
        )
        return result

    try:
        return web.json_response(await driver_pool.use(use_driver))
    except RuntimeError as exc:
        LOGGER.error("Driver pool unavailable: %s", exc)
        return web.json_response({"error": "Driver pool unavailable."}, status=503)
    except TimeoutException:
        LOGGER.warning("Request timed out for url=%s", url)
        return web.json_response({"error": "Page load timed out."}, status=504)
    except WebDriverException as exc:
        LOGGER.error("ChromeDriver failure for url=%s: %s", url, exc.msg)
        return web.json_response({"error": f"ChromeDriver failure: {exc.msg}"}, status=502)
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.exception("Unexpected extraction failure for url=%s", url)
        return web.json_response({"error": f"Unexpected error: {exc}"}, status=500)
