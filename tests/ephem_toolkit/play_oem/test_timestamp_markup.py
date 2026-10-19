"""Tests for small fractional seconds in read-only timestamp labels."""

from ephem_toolkit.play_oem.timestamp_markup import (
    set_timestamp_label,
    small_fraction_markup,
)


def test_small_fraction_markup_wraps_iso_fraction_and_timezone() -> None:
    assert (
        small_fraction_markup("UTC: 2026-10-19T19:41:40.501Z")
        == "UTC: 2026-10-19T19:41:40.<small>501</small>Z"
    )


def test_small_fraction_markup_wraps_elapsed_seconds() -> None:
    assert (
        small_fraction_markup("Elapsed: 12.345 s")
        == "Elapsed: 12.<small>345</small> s"
    )


def test_small_fraction_markup_leaves_text_without_fraction_unchanged() -> None:
    assert small_fraction_markup("2026-10-19T19:41:40Z") == "2026-10-19T19:41:40Z"


def test_set_timestamp_label_falls_back_when_markup_is_unavailable() -> None:
    class FakeLabel:
        def SetLabel(self, text: str) -> None:
            self.label = text

    label = FakeLabel()

    set_timestamp_label(label, "2026-10-19T19:41:40.501Z")

    assert label.label == "2026-10-19T19:41:40.501Z"
