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


def resolve_source_model(source_model: str, source_report: str | None) -> tuple[str, dict[str, Any] | None]:
    """Resolve an input model, optionally using a JSON source report."""
    report: dict[str, Any] | None = None
    if source_report:
        try:
            report = json.loads(Path(source_report).read_text(encoding="utf-8"))
        except OSError as error:
            raise ValueError(f"could not read source report '{source_report}': {error}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"source report '{source_report}' is not valid JSON: {error}") from error
        if not isinstance(report, dict):
            raise ValueError(f"source report '{source_report}' must contain a JSON object")

    if source_model != "auto":
        return source_model, report
    if report:
        report_provenance = report.get("provenance", {})
        if isinstance(report_provenance, dict) and report_provenance.get("source"):
            return str(report_provenance["source"]), report
    return "unknown", report


def comparison_residuals(comparisons: list[Any]) -> dict[str, float]:
    """Summarize position and velocity residuals from propagation comparisons."""
    if not comparisons:
        return {}
    positions = [float(item.pos_err_km) * 1000.0 for item in comparisons]
    velocities = [float(item.vel_err_m_s) for item in comparisons]
    return {
        "position_rms_m": (sum(value * value for value in positions) / len(positions)) ** 0.5,
        "position_max_m": max(positions),
        "velocity_rms_m_s": (sum(value * value for value in velocities) / len(velocities)) ** 0.5,
        "velocity_max_m_s": max(velocities),
    }


def write_fit_report(
    destination: str | Path,
    *,
    provenance: dict[str, Any],
    diagnostics: Any,
    configuration: dict[str, Any] | Any | None = None,
    source_report: dict[str, Any] | None = None,
    residuals: dict[str, float] | None = None,
) -> None:
    """Write a JSON fit report to a path or stdout (``-``)."""
    if configuration is not None and hasattr(configuration, "to_report_dict"):
        configuration = configuration.to_report_dict()
    report = {
        "provenance": provenance,
        "configuration": configuration or {},
        "diagnostics": asdict(diagnostics) if is_dataclass(diagnostics) else diagnostics,
    }
    report["status"] = "converged"
    fit_method = diagnostic_value(diagnostics, "fit_method")
    iterations = diagnostic_value(diagnostics, "iterations")
    if fit_method is not None:
        report["fit_method"] = fit_method
    if iterations is not None:
        report["iterations"] = iterations
    if source_report is not None:
        report["source_report"] = source_report
    if residuals:
        report["residuals"] = residuals
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if destination == "-":
        import sys

        sys.stdout.write(text)
    else:
        Path(destination).write_text(text, encoding="utf-8")
