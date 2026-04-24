import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse


def is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def looks_local_host(hostname: str) -> bool:
    lower_host = hostname.lower()
    if lower_host in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        ip = ipaddress.ip_address(lower_host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        try:
            resolved = socket.gethostbyname(lower_host)
            ip = ipaddress.ip_address(resolved)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except OSError:
            return True


def parse_bool_param(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise ValueError("Boolean value must be true/false.")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError("Boolean value must be true/false.")
