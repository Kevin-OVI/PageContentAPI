import os
from pathlib import Path


def _read_int_env(name: str, default: int, *, min_value: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc

    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}.")

    return value


LATEST_DRIVER_INDEX = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
DRIVER_ROOT = Path(__file__).resolve().parent.parent / ".drivers"
TIMEOUT_SECONDS = _read_int_env("TIMEOUT_SECONDS", 25, min_value=1)
MAX_MARKDOWN_CHARS = _read_int_env("MAX_MARKDOWN_CHARS", 100_000, min_value=1)
DRIVER_POOL_MIN_ACTIVE = _read_int_env("DRIVER_POOL_MIN_ACTIVE", 1, min_value=0)
DRIVER_POOL_MAX_ACTIVE = _read_int_env("DRIVER_POOL_MAX_ACTIVE", 4, min_value=1)
DRIVER_POOL_IDLE_TIMEOUT_SECONDS = _read_int_env(
    "DRIVER_POOL_IDLE_TIMEOUT_SECONDS",
    120,
    min_value=0,
)

if DRIVER_POOL_MAX_ACTIVE < DRIVER_POOL_MIN_ACTIVE:
    raise ValueError("DRIVER_POOL_MAX_ACTIVE must be greater than or equal to DRIVER_POOL_MIN_ACTIVE.")
