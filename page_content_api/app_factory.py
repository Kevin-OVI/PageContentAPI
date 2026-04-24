import asyncio
import logging

from aiohttp import web

from .browser import create_driver, download_latest_chromedriver
from .config import DEFAULT_MAX_MARKDOWN_CHARS, DEFAULT_TIMEOUT_SECONDS
from .routes import handle_extract, handle_health

LOGGER = logging.getLogger(__name__)


async def on_startup(app: web.Application) -> None:
    LOGGER.info("Server startup: initializing ChromeDriver")
    version, driver_path = await download_latest_chromedriver()
    app["driver_version"] = version
    app["driver_path"] = str(driver_path)
    app["driver"] = await asyncio.to_thread(
        create_driver,
        driver_path,
        int(app["timeout_seconds"]),
    )
    LOGGER.info("Server startup complete: ChromeDriver version=%s", version)


async def on_cleanup(app: web.Application) -> None:
    driver = app.get("driver")
    if driver is not None:
        LOGGER.info("Server shutdown: closing browser driver")
        await asyncio.to_thread(driver.quit)
        app["driver"] = None
        LOGGER.info("Server shutdown complete")


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
