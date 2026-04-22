import asyncio
import io
import ipaddress
import json
import logging
import platform
import re
import socket
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientSession, web
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as html_to_markdown
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

LATEST_DRIVER_INDEX = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)
DRIVER_ROOT = Path(__file__).resolve().parent / ".drivers"
DEFAULT_TIMEOUT_SECONDS = 25
DEFAULT_MAX_MARKDOWN_CHARS = 100_000

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class DriverDownloadError(RuntimeError):
    pass


def _resolve_driver_target() -> tuple[str, str]:
    system_name = platform.system().lower()
    machine = platform.machine().lower()

    if system_name == "windows":
        is_32_bit = machine in {"x86", "i386", "i686"}
        platform_key = "win32" if is_32_bit else "win64"
        return platform_key, "chromedriver.exe"

    if system_name == "darwin":
        if machine in {"arm64", "aarch64"}:
            return "mac-arm64", "chromedriver"
        if machine in {"x86_64", "amd64"}:
            return "mac-x64", "chromedriver"
        raise DriverDownloadError(f"Unsupported macOS architecture: {machine}")

    if system_name == "linux":
        if machine in {"x86_64", "amd64"}:
            return "linux64", "chromedriver"
        raise DriverDownloadError(f"Unsupported Linux architecture: {machine}")

    raise DriverDownloadError(f"Unsupported operating system: {platform.system()}")


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _looks_local_host(hostname: str) -> bool:
    lower_host = hostname.lower()
    if lower_host in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        ip = ipaddress.ip_address(lower_host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        try:
            resolved = socket.gethostbyname(lower_host)
            ip = ipaddress.ip_address(resolved)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except OSError:
            return True


def _parse_bool_param(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise ValueError("Boolean value must be true/false.")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError("Boolean value must be true/false.")


async def _download_latest_chromedriver() -> tuple[str, Path]:
    DRIVER_ROOT.mkdir(parents=True, exist_ok=True)

    platform_key, driver_filename = _resolve_driver_target()
    logger.info("Resolving latest ChromeDriver for platform=%s", platform_key)

    async with ClientSession() as session:
        async with session.get(LATEST_DRIVER_INDEX, timeout=30) as response:
            if response.status != 200:
                raise DriverDownloadError(
                    f"Failed to read driver index: HTTP {response.status}",
                )
            metadata = await response.json()

        stable = metadata.get("channels", {}).get("Stable", {})
        version = stable.get("version")
        downloads = stable.get("downloads", {}).get("chromedriver", [])
        candidate = next(
            (entry for entry in downloads if entry.get("platform") == platform_key),
            None,
        )

        if not candidate or not version:
            raise DriverDownloadError(
                f"No ChromeDriver download found for platform '{platform_key}'.",
            )

        target_dir = DRIVER_ROOT / version
        driver_path = target_dir / driver_filename
        if driver_path.exists():
            logger.info("Using cached ChromeDriver version=%s at %s", version, driver_path)
            return version, driver_path

        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading ChromeDriver version=%s", version)

        async with session.get(candidate["url"], timeout=60) as response:
            if response.status != 200:
                raise DriverDownloadError(
                    f"Failed to download driver zip: HTTP {response.status}",
                )
            zip_bytes = await response.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        driver_member = next(
            (
                name
                for name in zf.namelist()
                if name == driver_filename or name.endswith(f"/{driver_filename}")
            ),
            None,
        )
        if not driver_member:
            raise DriverDownloadError(
                f"Downloaded archive does not contain {driver_filename}",
            )

        with zf.open(driver_member) as source, driver_path.open("wb") as target:
            target.write(source.read())

    if platform.system().lower() != "windows":
        driver_path.chmod(driver_path.stat().st_mode | 0o111)

    logger.info("ChromeDriver downloaded and extracted to %s", driver_path)
    return version, driver_path

def _replace_media(
        content: Tag,
        tag_name: str,
        placeholder_prefix: str,
    ) -> None:
    for media in content.find_all(tag_name):
        alt_text = media.attrs.get('alt', '')
        if isinstance(alt_text, list):
            alt_text = " ".join(alt_text)
        media.replace_with(f"[{placeholder_prefix}: {alt_text}]" if alt_text else f"[{placeholder_prefix}]")


def _html_to_markdown(
        html: str,
        max_chars: int,
        include_links: bool,
        include_media: bool,
) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
    content = main or soup.body or soup

    if not include_links:
        for anchor in content.find_all("a"):
            anchor.replace_with(" ".join(anchor.stripped_strings))

    if not include_media:
        _replace_media(content, "img", "Image")
        _replace_media(content, "video", "Video")
        _replace_media(content, "audio", "Audio")


    markdown = html_to_markdown(str(content), heading_style="ATX")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

    if len(markdown) > max_chars:
        markdown = markdown[:max_chars].rstrip() + "\n\n...\n"

    return markdown


def _create_driver(driver_path: Path, timeout_seconds: int) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(executable_path=str(driver_path))
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(timeout_seconds)
    return driver


def _extract_markdown_with_tab(
        driver: webdriver.Chrome,
        url: str,
        timeout_seconds: int,
        max_chars: int,
        include_links: bool,
        include_media: bool,
) -> dict[str, Any]:
    logger.info("Starting page extraction for url=%s", url)
    try:
        driver.get(url)
        WebDriverWait(driver, timeout_seconds).until(
            lambda d: d.execute_script("return document.readyState") == "complete",
        )
        time.sleep(2)  # Allow additional time for dynamic content to load

        title = driver.title or ""
        final_url = driver.current_url
        markdown = _html_to_markdown(
            driver.page_source,
            max_chars=max_chars,
            include_links=include_links,
            include_media=include_media,
        )
        logger.info(
            "Extraction complete for url=%s (final_url=%s, markdown_chars=%d)",
            url,
            final_url,
            len(markdown),
        )

        return {
            "title": title,
            "url": final_url,
            "markdown": markdown,
        }
    finally:
        driver.get("about:blank")
        driver.delete_all_cookies()


async def handle_extract(request: web.Request) -> web.Response:
    logger.info("Received extract request method=%s path=%s", request.method, request.path)
    if request.method == "POST":
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            logger.warning("Rejecting extract request: invalid JSON body")
            return web.json_response({"error": "Invalid JSON body."}, status=400)
        url = str(payload.get("url", "")).strip()
        include_links_raw = payload.get("include_links")
        include_media_raw = payload.get("include_media")
    else:
        url = request.query.get("url", "").strip()
        include_links_raw = request.query.get("include_links")
        include_media_raw = request.query.get("include_media")

    try:
        include_links = _parse_bool_param(include_links_raw, default=True)
        include_media = _parse_bool_param(include_media_raw, default=True)
    except ValueError:
        logger.warning("Rejecting extract request: invalid include_links/include_media")
        return web.json_response(
            {"error": "include_links/include_media must be boolean values."},
            status=400,
        )

    if not _is_http_url(url):
        logger.warning("Rejecting extract request: invalid URL format")
        return web.json_response(
            {"error": "Provide a valid HTTP/HTTPS URL via query or JSON body."},
            status=400,
        )

    hostname = urlparse(url).hostname or ""
    if _looks_local_host(hostname):
        logger.warning("Rejecting extract request: local/private hostname=%s", hostname)
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
                _extract_markdown_with_tab,
                driver,
                url,
                timeout_seconds,
                max_chars,
                include_links,
                include_media,
            )
        logger.info("Request succeeded for hostname=%s", hostname)
        return web.json_response(result)
    except TimeoutException:
        logger.warning("Request timed out for url=%s", url)
        return web.json_response({"error": "Page load timed out."}, status=504)
    except WebDriverException as exc:
        logger.error("ChromeDriver failure for url=%s: %s", url, exc.msg)
        return web.json_response({"error": f"ChromeDriver failure: {exc.msg}"}, status=502)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Unexpected extraction failure for url=%s", url)
        return web.json_response({"error": f"Unexpected error: {exc}"}, status=500)


async def on_startup(app: web.Application) -> None:
    logger.info("Server startup: initializing ChromeDriver")
    version, driver_path = await _download_latest_chromedriver()
    app["driver_version"] = version
    app["driver_path"] = str(driver_path)
    app["driver"] = await asyncio.to_thread(
        _create_driver,
        driver_path,
        int(app["timeout_seconds"]),
    )
    logger.info("Server startup complete: ChromeDriver version=%s", version)


async def on_cleanup(app: web.Application) -> None:
    driver = app.get("driver")
    if driver is not None:
        logger.info("Server shutdown: closing browser driver")
        await asyncio.to_thread(driver.quit)
        app["driver"] = None
        logger.info("Server shutdown complete")


async def handle_health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_app() -> web.Application:
    app = web.Application()
    app["timeout_seconds"] = DEFAULT_TIMEOUT_SECONDS
    app["max_markdown_chars"] = DEFAULT_MAX_MARKDOWN_CHARS
    app["driver"] = None
    app["driver_lock"] = asyncio.Lock()

    app.router.add_get("/health", handle_health)
    app.router.add_get("/extract", handle_extract)
    app.router.add_post("/extract", handle_extract)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    logger.info("Starting PageContentAPI server on 0.0.0.0:8080")
    web.run_app(create_app(), host="0.0.0.0", port=8080)
