import logging

from aiohttp import web

LOGGER = logging.getLogger(__name__)


async def handle_shutdown(request: web.Request) -> web.Response:
    LOGGER.warning("Shutdown requested via /shutdown route")
    raise web.GracefulExit()
