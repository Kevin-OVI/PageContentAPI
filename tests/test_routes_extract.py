import pytest
from selenium.common import TimeoutException, WebDriverException

import page_content_api.routes.extract as extract_module
from page_content_api.app_factory import create_app


class FakeDriver:
    pass


class FakePool:
    def __init__(self, exc=None):
        self.exc = exc

    async def use(self, callback, allow_starting=True):
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
async def test_extract_rejects_invalid_json(aiohttp_client, app):
    client = await aiohttp_client(app)
    response = await client.post(
        "/extract",
        data="{",
        headers={"Content-Type": "application/json"},
    )

    assert response.status == 400


@pytest.mark.asyncio
async def test_extract_rejects_invalid_include_links(aiohttp_client, app):
    client = await aiohttp_client(app)
    response = await client.get("/extract?url=https://example.com&include_links=maybe")

    assert response.status == 400


@pytest.mark.asyncio
async def test_extract_rejects_invalid_url(aiohttp_client, app):
    client = await aiohttp_client(app)
    response = await client.get("/extract?url=not-a-url")

    assert response.status == 400


@pytest.mark.asyncio
async def test_extract_rejects_local_host(aiohttp_client, app):
    client = await aiohttp_client(app)
    response = await client.get("/extract?url=http://127.0.0.1")

    assert response.status == 400


@pytest.mark.asyncio
async def test_extract_success(aiohttp_client, app, monkeypatch):
    captured = {}

    def fake_extract_markdown(driver, url, timeout_seconds, max_chars, include_links, include_media):
        captured["args"] = (url, timeout_seconds, max_chars, include_links, include_media)
        return {"title": "Title", "url": url, "markdown": "Body"}

    monkeypatch.setattr(extract_module, "extract_markdown", fake_extract_markdown)
    app["driver_pool"] = FakePool()
    client = await aiohttp_client(app)

    response = await client.get(
        "/extract?url=https://example.com&include_links=false&include_media=true",
    )

    assert response.status == 200
    payload = await response.json()
    assert payload["title"] == "Title"
    assert captured["args"][0] == "https://example.com"
    assert captured["args"][3] is False
    assert captured["args"][4] is True


@pytest.mark.asyncio
async def test_extract_driver_pool_unavailable(aiohttp_client, app):
    app["driver_pool"] = FakePool(exc=RuntimeError("closed"))
    client = await aiohttp_client(app)
    response = await client.get("/extract?url=https://example.com")

    assert response.status == 503


@pytest.mark.asyncio
async def test_extract_timeout(aiohttp_client, app):
    app["driver_pool"] = FakePool(exc=TimeoutError("timeout"))
    client = await aiohttp_client(app)
    response = await client.get("/extract?url=https://example.com")

    assert response.status == 504


@pytest.mark.asyncio
async def test_extract_chromedriver_failure(aiohttp_client, app):
    app["driver_pool"] = FakePool(exc=WebDriverException("boom"))
    client = await aiohttp_client(app)
    response = await client.get("/extract?url=https://example.com")

    assert response.status == 502


@pytest.mark.asyncio
async def test_extract_timeout_exception(aiohttp_client, app):
    app["driver_pool"] = FakePool(exc=TimeoutException("timed out"))
    client = await aiohttp_client(app)
    response = await client.get("/extract?url=https://example.com")

    assert response.status == 504
