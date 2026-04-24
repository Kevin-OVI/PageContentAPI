from aiohttp import web


async def handle_health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})
