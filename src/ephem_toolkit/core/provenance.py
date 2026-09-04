"""Portable ephemeris provenance comments and JSON fit reports."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def provenance_comment(*, source: str, transformation: str, target_model: str) -> str:
    """Return the portable provenance comment defined by the conversion guide."""
    return (
        "EPHEMERIS_PROVENANCE: "
        f"source={source}; transformation={transformation}; target_model={target_model}"
    )


def fit_comment(*, span_s: float, samples: int, position_rms: float, velocity_rms: float | None = None) -> str:
    """Return a portable fit summary comment."""
    velocity = "unknown" if velocity_rms is None else f"{velocity_rms:g}"
    return (
        "EPHEMERIS_FIT: "
        f"span={span_s:g}s; samples={samples}; position_rms={position_rms:g}; "
        f"velocity_rms={velocity}"
    )


def diagnostic_value(diagnostics: Any, name: str, default: Any = None) -> Any:
    """Read a diagnostic from a dataclass-like object or a mapping."""
    if isinstance(diagnostics, dict):
        return diagnostics.get(name, default)
    return getattr(diagnostics, name, default)


def default_fit_report_path(input_path: str, output_path: str) -> Path | None:
    """Derive a report path from output, or input when output is stdout."""
    candidate = output_path if output_path != "-" else input_path
    if candidate == "-":
        return None
    return Path(candidate).with_suffix(".fit.json")


def write_fit_report(destination: str | Path, *, provenance: dict[str, Any], diagnostics: Any, configuration: dict[str, Any] | None = None) -> None:
    """Write a JSON fit report to a path or stdout (``-``)."""
    report = {
        "provenance": provenance,
        "configuration": configuration or {},
        "diagnostics": asdict(diagnostics) if is_dataclass(diagnostics) else diagnostics,
    }
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if destination == "-":
        import sys

        sys.stdout.write(text)
    else:
        Path(destination).write_text(text, encoding="utf-8")
