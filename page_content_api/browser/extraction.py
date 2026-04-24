import logging
import time
from typing import Any

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from .markdown_processing import html_fragment_to_markdown

LOGGER = logging.getLogger(__name__)


def extract_markdown_with_tab(
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
        driver.get("about:blank")
        driver.delete_all_cookies()

