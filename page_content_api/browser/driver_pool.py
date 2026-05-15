from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from selenium.common import WebDriverException
from selenium.webdriver.chrome.webdriver import WebDriver

from .driver_setup import create_driver, create_profile_dir_from_template, remove_profile_dir
from ..config import RESET_URL

LOGGER = logging.getLogger(__name__)


class _PoolDriverEntry:
    __slots__ = ("pool", "driver", "user_data_dir", "idle_event", "_reap_timer")

    def __init__(self, pool: DriverPool, driver: WebDriver, user_data_dir: Path | None):
        self.pool = pool
        self.driver = driver
        self.user_data_dir = user_data_dir
        self.idle_event = asyncio.Event()
        self.idle_event.set()
        self._reap_timer: asyncio.TimerHandle | None = None

    def cancel_reap_task(self):
        if self._reap_timer is not None:
            self._reap_timer.cancel()
            self._reap_timer = None

    def start_reap_task(self):
        if self._reap_timer is None:
            self._reap_timer = asyncio.get_event_loop().call_later(self.pool.idle_timeout_seconds, self.pool._reap_driver, self)

    def set_in_use(self):
        self.idle_event.clear()
        self.cancel_reap_task()

    def set_idle(self):
        self.idle_event.set()
        self.start_reap_task()

    async def close(self):
        try:
            await asyncio.to_thread(self.driver.quit)
        finally:
            await asyncio.to_thread(remove_profile_dir, self.user_data_dir)


class DriverPool:
    __slots__ = (
        "driver_path",
        "timeout_seconds",
        "min_active",
        "max_active",
        "idle_timeout_seconds",
        "_idle_drivers",
        "_in_use_drivers",
        "_release_condition",
        "_total_drivers",
        "_closed"
    )

    def __init__(self, driver_path: Path, timeout_seconds: int, min_active: int, max_active: int, idle_timeout_seconds: int):
        if min_active < 0:
            raise ValueError("min_active must be non-negative")
        if max_active <= 0:
            raise ValueError("max_active must be positive")
        if max_active < min_active:
            raise ValueError("max_active must be greater than or equal to min_active")

        self.driver_path = driver_path
        self.timeout_seconds = timeout_seconds
        self.min_active = min_active
        self.max_active = max_active
        self.idle_timeout_seconds = idle_timeout_seconds

        self._idle_drivers: set[_PoolDriverEntry] = set()
        self._in_use_drivers: set[_PoolDriverEntry] = set()
        self._release_condition = asyncio.Condition()
        self._total_drivers = 0
        self._closed = False

    async def initialize(self):
        LOGGER.info("Initializing driver pool with min_active=%d", self.min_active)
        entries = await asyncio.gather(*(self._start_driver() for _ in range(self.min_active)))
        self._idle_drivers.update(entries)
        self._total_drivers = self.min_active
        LOGGER.info(
            "Initialized driver pool min=%d max=%d idle_timeout=%ds",
            self.min_active,
            self.max_active,
            self.idle_timeout_seconds,
        )

    async def close(self):
        LOGGER.info("Closing driver pool")
        self._closed = True
        for entry in self._in_use_drivers:
            await entry.idle_event.wait()
        await asyncio.gather(*[entry.close() for entry in self._idle_drivers])
        LOGGER.info("Driver pool closed")

    @property
    def closed(self) -> bool:
        return self._closed

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def _start_driver(self) -> _PoolDriverEntry:
        LOGGER.info("Starting new driver instance")
        user_data_dir = await asyncio.to_thread(create_profile_dir_from_template)
        try:
            driver: WebDriver = await asyncio.to_thread(create_driver, self.driver_path, self.timeout_seconds, user_data_dir)
        except Exception:
            await asyncio.to_thread(remove_profile_dir, user_data_dir)
            raise
        driver.get(RESET_URL)
        LOGGER.info("Started new driver instance")
        return _PoolDriverEntry(self, driver, user_data_dir)

    def _reap_driver(self, entry: _PoolDriverEntry):
        if self._total_drivers > self.min_active and entry in self._idle_drivers:
            LOGGER.info("Reaping idle driver instance")
            self._idle_drivers.remove(entry)
            self._total_drivers -= 1
            asyncio.create_task(entry.close())

    def _remove_crashed_driver(self, entry: _PoolDriverEntry):
        if entry in self._in_use_drivers:
            LOGGER.warning("Removing crashed driver instance %s", entry.driver)
            self._in_use_drivers.remove(entry)
            self._total_drivers -= 1
            asyncio.create_task(entry.close())

    async def _acquire_driver(self, allow_starting: bool = True) -> _PoolDriverEntry:
        while True:
            if self._closed:
                raise RuntimeError("Driver pool is closed.")

            try:
                pool_driver = self._idle_drivers.pop()
            except KeyError:
                if self._total_drivers < self.max_active and allow_starting:
                    self._total_drivers += 1
                    try:
                        pool_driver = await self._start_driver()
                        pool_driver.set_in_use()
                        self._in_use_drivers.add(pool_driver)
                        return pool_driver
                    except Exception:
                        self._total_drivers -= 1
                        raise
                else:
                    async with self._release_condition:
                        await self._release_condition.wait()
            else:
                pool_driver.set_in_use()
                self._in_use_drivers.add(pool_driver)
                return pool_driver

    async def _release_driver(self, pool_driver: _PoolDriverEntry):
        pool_driver.set_idle()
        self._in_use_drivers.discard(pool_driver)
        self._idle_drivers.add(pool_driver)
        async with self._release_condition:
            self._release_condition.notify()

    async def use[T](self, callback: Callable[[WebDriver], T], allow_starting: bool = True) -> T:
        last_exception = None
        pool_driver = await self._acquire_driver(allow_starting)
        try:
            for attempt in range(3):
                try:
                    return await asyncio.to_thread(callback, pool_driver.driver)
                except WebDriverException as e:
                    LOGGER.exception("WebDriverException occurred, restarting driver...", exc_info=e)
                    last_exception = e
                    self._remove_crashed_driver(pool_driver)
                    pool_driver = await self._start_driver()
                    pool_driver.set_in_use()
                    self._in_use_drivers.add(pool_driver)
        finally:
            await self._release_driver(pool_driver)
        raise last_exception if last_exception else RuntimeError("Failed to acquire a working driver after multiple attempts.")
