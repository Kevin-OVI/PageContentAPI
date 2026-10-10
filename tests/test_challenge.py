import pytest
from selenium.common import JavascriptException

import page_content_api.browser.challenge as challenge_module
from page_content_api.browser.challenge import (
    CHALLENGE,
    ERROR_PAGE,
    CloudflareChallengeError,
    wait_for_challenge_to_clear,
)


class ScriptedDriver:
    """Answers detection calls from a queue; readyState is always complete."""

    current_url = "https://example.com"

    def __init__(self, detections):
        self.detections = list(detections)

    def execute_script(self, script):
        if "readyState" in script:
            return "complete"
        result = self.detections.pop(0) if len(self.detections) > 1 else self.detections[0]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(challenge_module.time, "sleep", lambda _: None)


def test_regular_page_returns_immediately():
    wait_for_challenge_to_clear(ScriptedDriver([None]), wait_seconds=0)


def test_error_page_fails_without_waiting():
    with pytest.raises(CloudflareChallengeError) as info:
        wait_for_challenge_to_clear(ScriptedDriver([ERROR_PAGE]), wait_seconds=60)
    assert info.value.kind == ERROR_PAGE


def test_challenge_that_clears():
    driver = ScriptedDriver([CHALLENGE, CHALLENGE, JavascriptException("navigating"), None])
    wait_for_challenge_to_clear(driver, wait_seconds=60)


def test_challenge_that_never_clears():
    with pytest.raises(CloudflareChallengeError) as info:
        wait_for_challenge_to_clear(ScriptedDriver([CHALLENGE]), wait_seconds=0)
    assert info.value.kind == CHALLENGE


def test_challenge_turning_into_error_page():
    with pytest.raises(CloudflareChallengeError) as info:
        wait_for_challenge_to_clear(ScriptedDriver([CHALLENGE, ERROR_PAGE]), wait_seconds=60)
    assert info.value.kind == ERROR_PAGE
