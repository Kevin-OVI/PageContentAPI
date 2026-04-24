import logging
import time
from typing import Any

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from .markdown_processing import html_fragment_to_markdown
from ..config import RESET_URL

LOGGER = logging.getLogger(__name__)


def _scroll_until_stable(driver: webdriver.Chrome, timeout_seconds: int) -> None:
    """Progressively scrolls down to trigger lazy-loaded content."""
    scroll_pause_seconds = 0.4
    max_scroll_steps = 60
    stable_height_limit = 3

    deadline = time.time() + max(1, timeout_seconds)
    last_height = driver.execute_script(
        "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);",
    )
    stable_height_count = 0

    for _ in range(max_scroll_steps):
        if time.time() >= deadline:
            LOGGER.warning("Progressive scroll stopped due to timeout window.")
            break

        next_offset = driver.execute_script("return window.pageYOffset + Math.max(window.innerHeight, 400);")
        driver.execute_script("window.scrollTo(0, arguments[0]);", next_offset)
        time.sleep(scroll_pause_seconds)

        current_height = driver.execute_script(
            "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);",
        )
        viewport_bottom = driver.execute_script("return window.pageYOffset + window.innerHeight;")

        if current_height <= last_height:
            stable_height_count += 1
        else:
            stable_height_count = 0

        # Attempt one hard scroll when near the bottom; some sites load on exact bottom reach.
        if viewport_bottom >= current_height - 2:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_seconds)
            current_height = driver.execute_script(
                "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);",
            )
            if current_height <= last_height:
                stable_height_count += 1

        if stable_height_count >= stable_height_limit:
            LOGGER.info("Progressive scroll finished after content height stabilized.")
            break

        last_height = current_height


def extract_markdown(
        driver: webdriver.Chrome,
        url: str,
        timeout_seconds: int,
        max_chars: int,
        include_links: bool,
        include_media: bool,
) -> dict[str, Any]:
    LOGGER.info("Starting page extraction for url=%s", url)
    try:
        driver.get(url)
        WebDriverWait(driver, timeout_seconds).until(
            lambda d: d.execute_script("return document.readyState") == "complete",
        )
        if driver.current_url == RESET_URL:
            LOGGER.error(f"Page failed to load and is still at {RESET_URL} for url=%s", url)
            raise TimeoutError("Page failed to load within the specified timeout.")
        _scroll_until_stable(driver, timeout_seconds)
        time.sleep(2)  # Allow additional time for dynamic content to load.

        title = driver.title or ""
        final_url = driver.current_url
        markdown = html_fragment_to_markdown(
            driver.page_source,
            max_chars=max_chars,
            include_links=include_links,
            include_media=include_media,
        )
        LOGGER.info(
            "Extraction complete for url=%s (final_url=%s, markdown_chars=%d)",
            url,
            final_url,
            len(markdown),
        )

        return {
            "title": title,
            "url": final_url,
            "markdown": markdown,
        }
    finally:
        driver.get(RESET_URL)
        driver.delete_all_cookies()
