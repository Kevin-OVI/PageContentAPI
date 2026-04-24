import asyncio
import json
import logging
from urllib.parse import urlparse

from aiohttp import web
from selenium.common import TimeoutException, WebDriverException

from ..browser import extract_markdown_with_tab
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

    timeout_seconds = int(request.app["timeout_seconds"])
    max_chars = int(request.app["max_markdown_chars"])
    driver = request.app["driver"]
    lock = request.app["driver_lock"]

    try:
        async with lock:
            result = await asyncio.to_thread(
                extract_markdown_with_tab,
                driver,
                url,
                timeout_seconds,
                max_chars,
                include_links,
                include_media,
            )
        LOGGER.info("Request succeeded for hostname=%s", hostname)
        return web.json_response(result)
    except TimeoutException:
        LOGGER.warning("Request timed out for url=%s", url)
        return web.json_response({"error": "Page load timed out."}, status=504)
    except WebDriverException as exc:
        LOGGER.error("ChromeDriver failure for url=%s: %s", url, exc.msg)
        return web.json_response({"error": f"ChromeDriver failure: {exc.msg}"}, status=502)
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.exception("Unexpected extraction failure for url=%s", url)
        return web.json_response({"error": f"Unexpected error: {exc}"}, status=500)
