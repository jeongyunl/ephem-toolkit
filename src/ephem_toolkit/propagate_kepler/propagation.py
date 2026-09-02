"""Kepler input loading and propagation implementation."""

from __future__ import annotations

import datetime as dt
import io
import pathlib
import sys

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.propagator.kepler as kepler
import ephem_toolkit.core.time_utils as time_utils
from ephem_toolkit.core.propagator import (
    KeplerPropagator,
    KeplerianState,
    OutputMode,
)


def read_kepler_input(source: str | None):
    """Read Keplerian elements and metadata from an OPM file or stdin."""
    source = source or "-"
    if source == "-":
        if sys.stdin.isatty():
            raise ValueError(
                "OPM input not provided. Pass <input_opm> or pipe OPM content on stdin."
            )
        text = sys.stdin.read()
        if not text.strip():
            raise ValueError("Empty stdin input. Provide OPM content on stdin.")
        message = opm.CcsdsOpm.from_source(io.StringIO(text))
    else:
        message = opm.CcsdsOpm.from_source(pathlib.Path(source).expanduser().resolve())
    elements = message.keplerian_elements
    if elements is None:
        raise ValueError("OPM input does not contain Keplerian elements")
    if elements.true_anomaly is not None:
        anomaly = elements.true_anomaly
    elif elements.mean_anomaly is not None:
        anomaly = np.degrees(
            kepler.mean_to_true_anomaly(
                np.radians(elements.mean_anomaly), elements.eccentricity
            )
        )
    else:
        raise ValueError("OPM input does not contain an anomaly")
    epoch = time_utils.iso8601_to_datetime(message.state_vector.epoch)
    state = np.array(
        [
            elements.semi_major_axis,
            elements.eccentricity,
            np.radians(elements.inclination),
            np.radians(elements.arg_of_pericenter),
            np.radians(elements.ra_of_asc_node),
            np.radians(anomaly),
        ],
        dtype=float,
    )
    metadata = {
        out: str(message.metadata[key])
        for out, key in (
            ("object_name", "OBJECT_NAME"),
            ("ref_frame", "REF_FRAME"),
            ("center_name", "CENTER_NAME"),
            ("time_system", "TIME_SYSTEM"),
        )
    }
    return epoch, state, metadata


def propagate_kepler_elements(
    initial_epoch: dt.datetime,
    initial_kepler_km,
    duration_s: float,
    step_s: float,
    data_only: bool,
    output_metadata: dict[str, str],
    output_path: str = "-",
) -> None:
    """Propagate Keplerian elements and write the resulting OEM."""
    elements = initial_kepler_km.astype(np.float64).copy()
    elements[kepler.SEMI_MAJOR_AXIS_INDEX] *= 1000.0
    epoch = time_utils.datetime_to_tt_s(initial_epoch)
    propagator = KeplerPropagator(
        initial_state=KeplerianState(elements=elements, epoch_s=epoch)
    )
    states = []
    current = 0.0
    while current <= duration_s + 1.0e-12:
        result = propagator.propagate_to(epoch + current, output=OutputMode.FINAL)
        if not isinstance(result, tuple):
            raise RuntimeError("Kepler propagation did not return a final state")
        states.append(result)
        current += step_s
    stream = (
        sys.stdout if output_path == "-" else open(output_path, "w", encoding="utf-8")
    )
    try:
        message = (
            oem.CcsdsOem.from_states(states, **output_metadata)
            if not data_only
            else oem.CcsdsOem.from_states(states)
        )
        if data_only:
            message.write_states(stream)
        else:
            message.write(stream)
    finally:
        if output_path != "-":
            stream.close()
