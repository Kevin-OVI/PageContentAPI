from pathlib import Path

import pytest
from aiohttp import web

import page_content_api.app_factory as app_factory


class DummyPool:
    def __init__(self, driver_path, timeout_seconds, min_active, max_active, idle_timeout_seconds):
        self.init_args = (driver_path, timeout_seconds, min_active, max_active, idle_timeout_seconds)
        self.initialized = False
        self.closed = False

    async def initialize(self):
        self.initialized = True

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_on_startup_and_cleanup(monkeypatch):
    async def fake_download():
        return "123.0.0", Path("C:/tmp/chromedriver")

    monkeypatch.setattr(app_factory, "download_chromedriver", fake_download)
    monkeypatch.setattr(app_factory, "DriverPool", DummyPool)

    app = web.Application()
    await app_factory.on_startup(app)

    pool = app["driver_pool"]
    assert isinstance(pool, DummyPool)
    assert pool.initialized is True

    await app_factory.on_cleanup(app)
    assert pool.closed is True
    assert app["driver_pool"] is None


def test_create_app_routes():
    app = app_factory.create_app()
    route_paths = {route.resource.canonical for route in app.router.routes()}

    assert "/health" in route_paths
    assert "/extract" in route_paths


def test_create_app_routes_shutdown_toggle(monkeypatch):
    monkeypatch.setattr(app_factory, "ENABLE_SHUTDOWN_ROUTE", True)
    app_enabled = app_factory.create_app()
    enabled_paths = {route.resource.canonical for route in app_enabled.router.routes()}
    assert "/shutdown" in enabled_paths

    monkeypatch.setattr(app_factory, "ENABLE_SHUTDOWN_ROUTE", False)
    app_disabled = app_factory.create_app()
    disabled_paths = {route.resource.canonical for route in app_disabled.router.routes()}
    assert "/shutdown" not in disabled_paths
