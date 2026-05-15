import logging

from aiohttp import web

from ..browser import DriverPool

LOGGER = logging.getLogger(__name__)


async def handle_health(request: web.Request) -> web.Response:
    driver_pool = request.app.get("driver_pool")
    if driver_pool is None or (isinstance(driver_pool, DriverPool) and driver_pool.closed):
        return web.json_response(
            {"status": "unavailable", "reason": "driver_pool_uninitialized"},
            status=503,
        )

    try:
        await driver_pool.use(lambda driver: driver.execute_script("return 1"), allow_starting=False)
    except Exception as exc:
        LOGGER.warning("Health check failed: %s", exc)
        return web.json_response(
            {"status": "unavailable", "reason": "driver_pool_unhealthy"},
            status=503,
        )

    return web.json_response({"status": "ok"})
