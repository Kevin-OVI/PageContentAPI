import logging

from aiohttp import web

from .browser import DriverPool, download_latest_chromedriver
from .config import (
    DRIVER_POOL_IDLE_TIMEOUT_SECONDS,
    DRIVER_POOL_MAX_ACTIVE,
    DRIVER_POOL_MIN_ACTIVE,
    TIMEOUT_SECONDS,
)
from .routes import handle_extract, handle_health

LOGGER = logging.getLogger(__name__)


async def on_startup(app: web.Application) -> None:
    LOGGER.info("Server startup: initializing ChromeDriver")
    version, driver_path = await download_latest_chromedriver()
    pool = DriverPool(
        driver_path,
        TIMEOUT_SECONDS,
        DRIVER_POOL_MIN_ACTIVE,
        DRIVER_POOL_MAX_ACTIVE,
        DRIVER_POOL_IDLE_TIMEOUT_SECONDS,
    )
    await pool.initialize()
    app["driver_pool"] = pool
    LOGGER.info("Server startup complete: ChromeDriver version=%s", version)


async def on_cleanup(app: web.Application) -> None:
    driver_pool = app.get("driver_pool")
    if driver_pool is not None:
        LOGGER.info("Server shutdown: closing driver pool")
        await driver_pool.close()
        app["driver_pool"] = None
        LOGGER.info("Server shutdown complete")


def create_app() -> web.Application:
    app = web.Application()
    app["driver_pool"] = None

    app.router.add_get("/health", handle_health)
    app.router.add_get("/extract", handle_extract)
    app.router.add_post("/extract", handle_extract)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app
