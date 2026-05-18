import pytest

from page_content_api.validation import is_http_url, looks_local_host, parse_bool_param


def test_is_http_url():
    assert is_http_url("http://example.com")
    assert is_http_url("https://example.com/path")
    assert not is_http_url("ftp://example.com")
    assert not is_http_url("example.com")
    assert not is_http_url("http:///nohost")


def test_looks_local_host_basic():
    assert looks_local_host("localhost")
    assert looks_local_host("127.0.0.1")
    assert looks_local_host("::1")
    assert looks_local_host("192.168.0.1")
    assert looks_local_host("10.0.0.1")
    assert not looks_local_host("8.8.8.8")


def test_looks_local_host_unresolvable():
    assert looks_local_host("not-a-real-host.invalid")


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("no", False),
        ("on", True),
        ("off", False),
        ("Y", True),
        ("N", False),
        (1, True),
        (0, False),
    ],
)
def test_parse_bool_param_valid(value, expected):
    assert parse_bool_param(value, default=False) is expected


def test_parse_bool_param_default():
    assert parse_bool_param(None, default=True) is True
    assert parse_bool_param(None, default=False) is False


def test_parse_bool_param_invalid():
    with pytest.raises(ValueError):
        parse_bool_param("maybe", default=True)
    with pytest.raises(ValueError):
        parse_bool_param(2, default=True)
