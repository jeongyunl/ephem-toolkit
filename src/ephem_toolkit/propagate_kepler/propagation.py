"""Kepler input loading and propagation implementation."""

from __future__ import annotations

import datetime as dt
import io
import pathlib
import sys

import numpy as np

import ephem_toolkit.core.ccsds.oem as oem
import ephem_toolkit.core.ccsds.opm as opm
import ephem_toolkit.core.provenance as provenance
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
            ("object_id", "OBJECT_ID"),
            ("ref_frame", "REF_FRAME"),
            ("center_name", "CENTER_NAME"),
            ("time_system", "TIME_SYSTEM"),
        )
    }
    metadata["ref_frame_epoch"] = str(message.metadata.get("REF_FRAME_EPOCH", ""))
    metadata["classification"] = message.header.classification
    metadata["message_id"] = message.header.message_id
    covariance = None
    if message.covariance is not None:
        covariance = oem.OemCovariance(
            epoch=message.state_vector.epoch,
            matrix=message.covariance.matrix.copy(),
            ref_frame=message.covariance.ref_frame,
        )
    return epoch, state, metadata, tuple(message.header.comments), covariance


def propagate_kepler_elements(
    initial_epoch: dt.datetime,
    initial_kepler_km,
    duration_s: float,
    step_s: float,
    data_only: bool,
    output_metadata: dict[str, str],
    output_path: str = "-",
    source_comments: tuple[str, ...] = (),
    covariance: oem.OemCovariance | None = None,
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
        oem_metadata = {
            key: value
            for key, value in output_metadata.items()
            if key not in {"classification", "message_id", "ref_frame_epoch"}
        }
        message = (
            oem.CcsdsOem.from_states(
                states,
                **oem_metadata,
                covariances=[covariance] if covariance is not None else None,
            )
            if not data_only
            else oem.CcsdsOem.from_states(states)
        )
        if not data_only:
            message.meta.ref_frame_epoch = output_metadata.get("ref_frame_epoch", "")
        if data_only:
            message.write_states(stream)
        else:
            message.header.classification = output_metadata.get("classification", "")
            message.header.message_id = output_metadata.get("message_id", "")
            message.meta.comments.extend(source_comments)
            message.meta.comments.append(
                provenance.provenance_comment(
                    source="OPM",
                    transformation="propagation",
                    target_model="two-body-kepler",
                )
            )
            message.write(stream)
    finally:
        if output_path != "-":
            stream.close()
