import io
import logging
import platform
import re
import subprocess
import zipfile
from pathlib import Path

from aiohttp import ClientSession
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from ..config import (
    DRIVER_ROOT,
    LATEST_BY_MILESTONE_INDEX,
    LATEST_DRIVER_INDEX,
    LATEST_PATCH_BY_BUILD_INDEX,
)

LOGGER = logging.getLogger(__name__)
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)")


class DriverDownloadError(RuntimeError):
    pass


def _extract_version(text: str) -> str | None:
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _run_command(command: list[str]) -> str | None:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if process.returncode != 0:
        return None

    return process.stdout or process.stderr


def detect_local_chrome_version() -> str | None:
    system_name = platform.system().lower()

    if system_name == "windows":
        commands = [
            ["reg", "query", r"HKCU\Software\Google\Chrome\BLBeacon", "/v", "version"],
            ["reg", "query", r"HKLM\Software\Google\Chrome\BLBeacon", "/v", "version"],
            ["reg", "query", r"HKLM\Software\WOW6432Node\Google\Chrome\BLBeacon", "/v", "version"],
        ]
    elif system_name == "darwin":
        commands = [
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
        ]
    elif system_name == "linux":
        commands = [
            ["google-chrome", "--version"],
            ["google-chrome-stable", "--version"],
            ["chromium", "--version"],
            ["chromium-browser", "--version"],
        ]
    else:
        return None

    for command in commands:
        output = _run_command(command)
        if not output:
            continue

        version = _extract_version(output)
        if version:
            return version

    return None


def _select_platform_candidate(downloads: list[dict], platform_key: str) -> dict | None:
    return next(
        (entry for entry in downloads if entry.get("platform") == platform_key),
        None,
    )


async def _read_json(session: ClientSession, url: str, timeout: int, label: str) -> dict:
    async with session.get(url, timeout=timeout) as response:
        if response.status != 200:
            raise DriverDownloadError(f"Failed to read {label}: HTTP {response.status}")
        return await response.json()


async def _resolve_download_for_local_chrome(
        session: ClientSession,
        platform_key: str,
) -> tuple[str, dict] | None:
    local_version = detect_local_chrome_version()
    if not local_version:
        LOGGER.info("Could not detect installed Chrome version; falling back to stable channel")
        return None

    parts = local_version.split(".")
    if len(parts) < 3:
        LOGGER.info("Detected Chrome version has unexpected format (%s); falling back to stable channel", local_version)
        return None

    build_key = ".".join(parts[:3])
    milestone = parts[0]
    LOGGER.info("Detected local Chrome version=%s (build=%s, milestone=%s)", local_version, build_key, milestone)

    try:
        build_metadata = await _read_json(
            session,
            LATEST_PATCH_BY_BUILD_INDEX,
            30,
            "patch-by-build index",
        )
        build_entry = build_metadata.get("builds", {}).get(build_key, {})
        version = build_entry.get("version")
        downloads = build_entry.get("downloads", {}).get("chromedriver", [])
        candidate = _select_platform_candidate(downloads, platform_key)
        if version and candidate:
            LOGGER.info("Resolved ChromeDriver version=%s from build=%s", version, build_key)
            return version, candidate
    except DriverDownloadError as exc:
        LOGGER.warning("Failed to resolve ChromeDriver by build: %s", exc)

    try:
        milestone_metadata = await _read_json(
            session,
            LATEST_BY_MILESTONE_INDEX,
            30,
            "milestone index",
        )
        milestone_entry = milestone_metadata.get("milestones", {}).get(milestone, {})
        version = milestone_entry.get("version")
        downloads = milestone_entry.get("downloads", {}).get("chromedriver", [])
        candidate = _select_platform_candidate(downloads, platform_key)
        if version and candidate:
            LOGGER.info("Resolved ChromeDriver version=%s from milestone=%s", version, milestone)
            return version, candidate
    except DriverDownloadError as exc:
        LOGGER.warning("Failed to resolve ChromeDriver by milestone: %s", exc)

    LOGGER.info("No ChromeDriver mapping found for local Chrome version=%s; using stable channel", local_version)
    return None


def resolve_driver_target() -> tuple[str, str]:
    system_name = platform.system().lower()
    machine = platform.machine().lower()

    if system_name == "windows":
        is_32_bit = machine in {"x86", "i386", "i686"}
        platform_key = "win32" if is_32_bit else "win64"
        return platform_key, "chromedriver.exe"

    if system_name == "darwin":
        if machine in {"arm64", "aarch64"}:
            return "mac-arm64", "chromedriver"
        if machine in {"x86_64", "amd64"}:
            return "mac-x64", "chromedriver"
        raise DriverDownloadError(f"Unsupported macOS architecture: {machine}")

    if system_name == "linux":
        if machine in {"x86_64", "amd64"}:
            return "linux64", "chromedriver"
        raise DriverDownloadError(f"Unsupported Linux architecture: {machine}")

    raise DriverDownloadError(f"Unsupported operating system: {platform.system()}")


async def download_latest_chromedriver() -> tuple[str, Path]:
    DRIVER_ROOT.mkdir(parents=True, exist_ok=True)

    platform_key, driver_filename = resolve_driver_target()
    LOGGER.info("Resolving ChromeDriver for platform=%s", platform_key)

    async with ClientSession() as session:
        resolved = await _resolve_download_for_local_chrome(session, platform_key)
        if resolved is None:
            metadata = await _read_json(session, LATEST_DRIVER_INDEX, 30, "driver index")
            stable = metadata.get("channels", {}).get("Stable", {})
            version = stable.get("version")
            downloads = stable.get("downloads", {}).get("chromedriver", [])
            candidate = _select_platform_candidate(downloads, platform_key)
            if not candidate or not version:
                raise DriverDownloadError(
                    f"No ChromeDriver download found for platform '{platform_key}'.",
                )
            LOGGER.info("Using stable-channel ChromeDriver version=%s", version)
        else:
            version, candidate = resolved

        target_dir = DRIVER_ROOT / version
        driver_path = target_dir / driver_filename
        if driver_path.exists():
            LOGGER.info("Using cached ChromeDriver version=%s at %s", version, driver_path)
            return version, driver_path

        target_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.info("Downloading ChromeDriver version=%s", version)

        async with session.get(candidate["url"], timeout=60) as response:
            if response.status != 200:
                raise DriverDownloadError(
                    f"Failed to download driver zip: HTTP {response.status}",
                )
            zip_bytes = await response.read()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        driver_member = next(
            (
                name
                for name in zf.namelist()
                if name == driver_filename or name.endswith(f"/{driver_filename}")
            ),
            None,
        )
        if not driver_member:
            raise DriverDownloadError(
                f"Downloaded archive does not contain {driver_filename}",
            )

        with zf.open(driver_member) as source, driver_path.open("wb") as target:
            target.write(source.read())

    if platform.system().lower() != "windows":
        driver_path.chmod(driver_path.stat().st_mode | 0o111)

    LOGGER.info("ChromeDriver downloaded and extracted to %s", driver_path)
    return version, driver_path


def create_driver(driver_path: Path, timeout_seconds: int) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(executable_path=str(driver_path))
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(timeout_seconds)
    return driver
