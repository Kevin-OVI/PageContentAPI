import io
import logging
import platform
import zipfile
from pathlib import Path

from aiohttp import ClientSession
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from ..config import DRIVER_ROOT, LATEST_DRIVER_INDEX

LOGGER = logging.getLogger(__name__)


class DriverDownloadError(RuntimeError):
    pass


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
    LOGGER.info("Resolving latest ChromeDriver for platform=%s", platform_key)

    async with ClientSession() as session:
        async with session.get(LATEST_DRIVER_INDEX, timeout=30) as response:
            if response.status != 200:
                raise DriverDownloadError(
                    f"Failed to read driver index: HTTP {response.status}",
                )
            metadata = await response.json()

        stable = metadata.get("channels", {}).get("Stable", {})
        version = stable.get("version")
        downloads = stable.get("downloads", {}).get("chromedriver", [])
        candidate = next(
            (entry for entry in downloads if entry.get("platform") == platform_key),
            None,
        )

        if not candidate or not version:
            raise DriverDownloadError(
                f"No ChromeDriver download found for platform '{platform_key}'.",
            )

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
