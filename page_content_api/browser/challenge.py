import logging
import time

from selenium import webdriver
from selenium.common import WebDriverException

LOGGER = logging.getLogger(__name__)

CHALLENGE = "challenge"
ERROR_PAGE = "error_page"

# Structural markers rather than titles, which Cloudflare localizes. Neither the
# /cdn-cgi/challenge-platform/ scripts nor the mere presence of window._cf_chl_opt are used:
# Cloudflare injects both into normal pages, whereas only the challenge page sets cType/cRay on it.
_DETECT_SCRIPT = """
if (document.getElementById('cf-error-details')) return 'error_page';
const opt = window._cf_chl_opt;
if ((opt && (opt.cType || opt.cRay))
        || document.getElementById('challenge-form')
        || document.getElementById('challenge-running')
        || document.getElementById('challenge-stage')) return 'challenge';
return null;
"""

_POLL_SECONDS = 0.5


class CloudflareChallengeError(Exception):
    """Raised when the loaded page is a Cloudflare challenge or error page instead of the content."""

    def __init__(self, kind: str, url: str):
        super().__init__(f"Cloudflare {kind} at {url}")
        self.kind = kind
        self.url = url


def detect_challenge(driver: webdriver.Chrome) -> str | None:
    """Returns CHALLENGE, ERROR_PAGE, or None for a regular page."""
    return driver.execute_script(_DETECT_SCRIPT)


def wait_for_challenge_to_clear(driver: webdriver.Chrome, wait_seconds: int) -> None:
    """Waits for a self-solving challenge to redirect to the real page.

    Error pages (blocks, origin errors) never clear, so they fail immediately.
    """
    kind = detect_challenge(driver)
    if kind is None:
        return
    if kind == ERROR_PAGE:
        LOGGER.warning("Cloudflare error page detected for url=%s", driver.current_url)
        raise CloudflareChallengeError(kind, driver.current_url)

    LOGGER.info("Cloudflare challenge detected for url=%s; waiting up to %ds", driver.current_url, wait_seconds)
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        time.sleep(_POLL_SECONDS)
        try:
            kind = detect_challenge(driver)
            ready = driver.execute_script("return document.readyState") == "complete"
        except WebDriverException:
            # The challenge's redirect can tear down the document mid-script.
            continue
        if kind is None and ready:
            LOGGER.info("Cloudflare challenge cleared for url=%s", driver.current_url)
            return
        if kind == ERROR_PAGE:
            break

    LOGGER.warning("Cloudflare %s did not clear for url=%s", kind, driver.current_url)
    raise CloudflareChallengeError(kind or CHALLENGE, driver.current_url)
