import sys

import pytest

from ephem_toolkit.core.app_utils import (
    activate_application,
    activate_macos_application,
)


def test_activate_application_returns_false_outside_macos() -> None:
    assert activate_application("linux") is False
    assert activate_application("win32") is False


def test_activate_macos_application_returns_false_outside_macos() -> None:
    assert activate_macos_application("linux") is False


def test_activate_application_uses_current_platform(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert activate_application() is False


@pytest.mark.skipif(not sys.platform.startswith("darwin"), reason="macOS-only")
def test_activate_macos_application_reports_runtime_result() -> None:
    assert isinstance(activate_macos_application(), bool)
