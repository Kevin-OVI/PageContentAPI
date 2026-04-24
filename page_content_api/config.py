from pathlib import Path

LATEST_DRIVER_INDEX = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)
DRIVER_ROOT = Path(__file__).resolve().parent.parent / ".drivers"
DEFAULT_TIMEOUT_SECONDS = 25
DEFAULT_MAX_MARKDOWN_CHARS = 100_000

