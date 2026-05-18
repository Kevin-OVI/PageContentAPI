import pytest

from page_content_api.app_factory import create_app


class FakeDriver:
    def execute_script(self, script):
        return 1


class FakePool:
    def __init__(self, exc=None):
        self.exc = exc
        self.last_allow_starting = None

    async def use(self, callback, allow_starting=True):
        self.last_allow_starting = allow_starting
        if self.exc is not None:
            raise self.exc
        return callback(FakeDriver())


@pytest.fixture
def app():
    app = create_app()
    app.on_startup.clear()
    app.on_cleanup.clear()
    return app


@pytest.mark.asyncio
async def test_health_uninitialized(aiohttp_client, app):
    client = await aiohttp_client(app)
    response = await client.get("/health")

    assert response.status == 503
    payload = await response.json()
    assert payload["status"] == "unavailable"


@pytest.mark.asyncio
async def test_health_unhealthy(aiohttp_client, app):
    app["driver_pool"] = FakePool(exc=RuntimeError("boom"))
    client = await aiohttp_client(app)
    response = await client.get("/health")

    assert response.status == 503
    payload = await response.json()
    assert payload["reason"] == "driver_pool_unhealthy"


@pytest.mark.asyncio
async def test_health_ok(aiohttp_client, app):
    app["driver_pool"] = FakePool()
    client = await aiohttp_client(app)
    response = await client.get("/health")

    assert response.status == 200
    payload = await response.json()
    assert payload == {"status": "ok"}
    assert app["driver_pool"].last_allow_starting is False
