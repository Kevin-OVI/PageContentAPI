import logging

from aiohttp import web

from .browser import DriverPool, download_chromedriver
from .config import (
    DRIVER_POOL_IDLE_TIMEOUT_SECONDS,
    DRIVER_POOL_MAX_ACTIVE,
    DRIVER_POOL_MIN_ACTIVE,
    TIMEOUT_SECONDS,
    ENABLE_SHUTDOWN_ROUTE,
)
from .routes import handle_extract, handle_health, handle_shutdown

LOGGER = logging.getLogger(__name__)


async def on_startup(app: web.Application) -> None:
    LOGGER.info("Server startup: initializing ChromeDriver")
    version, driver_path = await download_chromedriver()
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
    if ENABLE_SHUTDOWN_ROUTE:
        app.router.add_post("/shutdown", handle_shutdown)
        LOGGER.warning("Shutdown route enabled: POST /shutdown")

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app
