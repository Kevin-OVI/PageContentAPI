from argparse import ArgumentTypeError

import pytest

from app import _parse_host, _parse_port


def test_parse_port_valid():
    assert _parse_port("8080") == 8080


def test_parse_port_invalid():
    with pytest.raises(ArgumentTypeError):
        _parse_port("nope")
    with pytest.raises(ArgumentTypeError):
        _parse_port("70000")


def test_parse_host():
    assert _parse_host("127.0.0.1") == "127.0.0.1"
    with pytest.raises(ArgumentTypeError):
        _parse_host("   ")
