"""Read, parse, and write CCSDS Orbit Ephemeris Message (OEM) files.

Provides low-level functions (:func:`read_oem`, :func:`write_oem`) that
operate on plain dictionaries, and a structured :class:`CcsdsOem` class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO, Union

import numpy as np

# ===================================================================
# Internal helpers
# ===================================================================


def _parse_kv_line(line: str) -> tuple[str, str] | None:
    """Return (key, value) from ``KEY = VALUE`` lines, or *None*."""
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    return key.strip(), value.strip()


def _parse_epoch(epoch_str: str) -> datetime:
    """Parse an ISO-8601-ish epoch string into a :class:`datetime`."""
    s = epoch_str.strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


def _is_state_line(line: str) -> bool:
    """Heuristic: a state line starts with a date-like token."""
    token = line.split()[0] if line.split() else ""
    return len(token) >= 10 and token[4:5] == "-"


_META_KEY_ORDER = [
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "TIME_SYSTEM",
    "START_TIME",
    "USEABLE_START_TIME",
    "USEABLE_STOP_TIME",
    "STOP_TIME",
    "INTERPOLATION",
    "INTERPOLATION_DEGREE",
]


# ===================================================================
# Low-level reader (dict-based)
# ===================================================================


def read_oem(
    source: Union[IO[str], str, Path],
) -> tuple[dict, dict, dict[datetime, np.ndarray]]:
    """Read an OEM file and return *(header, meta, states)*."""
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8") as fh:
            return read_oem(fh)

    header: dict = {}
    meta: dict = {}
    states: dict[datetime, np.ndarray] = {}
    in_meta = False

    for raw_line in source:
        line = raw_line.strip()
        if not line:
            continue

        if line == "META_START":
            in_meta = True
            continue
        if line == "META_STOP":
            in_meta = False
            continue

        if line.startswith("COMMENT"):
            comment_text = line[len("COMMENT") :].strip()
            target = meta if in_meta else header
            target.setdefault("COMMENT", [])
            target["COMMENT"].append(comment_text)
            continue

        kv = _parse_kv_line(line)
        if kv is not None and (in_meta or not _is_state_line(line)):
            key, value = kv
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
            if in_meta:
                meta[key] = value
            else:
                header[key] = value
            continue

        if _is_state_line(line):
            parts = line.split()
            if len(parts) < 7:
                continue
            epoch = _parse_epoch(parts[0])
            states[epoch] = np.array([float(v) for v in parts[1:7]])

    return header, meta, states


# ===================================================================
# Low-level writer (dict-based)
# ===================================================================


def write_oem(
    dest: Union[IO[str], str, Path],
    header: dict,
    meta: dict,
    states: dict[datetime, np.ndarray],
) -> None:
    """Write an OEM file from *(header, meta, states)* dicts."""
    if isinstance(dest, (str, Path)):
        with open(dest, "w", encoding="utf-8") as fh:
            return write_oem(fh, header, meta, states)

    w = dest.write

    version = header.get("CCSDS_OEM_VERS", 2.0)
    w(f"CCSDS_OEM_VERS = {version}\n")
    w("\n")

    for comment in header.get("COMMENT", []):
        w(f"COMMENT {comment}\n")
    if header.get("COMMENT"):
        w("\n")

    if "CREATION_DATE" in header:
        w(f"CREATION_DATE  = {header['CREATION_DATE']}\n")
    if "ORIGINATOR" in header:
        w(f"ORIGINATOR     = {header['ORIGINATOR']}\n")
    w("\n")

    w("META_START\n")
    for comment in meta.get("COMMENT", []):
        w(f"COMMENT {comment}\n")

    meta_keys = [k for k in _META_KEY_ORDER if k in meta]
    extra_keys = [k for k in meta if k not in _META_KEY_ORDER and k != "COMMENT"]
    all_keys = meta_keys + extra_keys
    pad = max((len(k) for k in all_keys), default=0)

    for key in all_keys:
        w(f"{key:<{pad}} = {meta[key]}\n")

    w("META_STOP\n")
    w("\n")

    for epoch in states:
        sv = states[epoch]
        epoch_str = epoch.strftime("%Y-%m-%dT%H:%M:%S.%f")
        vals = " ".join(f"{v:.15g}" for v in sv)
        w(f"{epoch_str} {vals}\n")


# ===================================================================
# Structured classes
# ===================================================================


@dataclass
class OemHeader:
    version: float = 0.0
    comments: list[str] = field(default_factory=list)
    creation_date: str = ""
    originator: str = ""


@dataclass
class OemMeta:
    object_name: str = ""
    object_id: str = ""
    center_name: str = ""
    ref_frame: str = ""
    time_system: str = ""
    start_time: str = ""
    stop_time: str = ""
    useable_start_time: str = ""
    useable_stop_time: str = ""
    interpolation: str = ""
    interpolation_degree: int = 0
    comments: list[str] = field(default_factory=list)


class CcsdsOem:
    def __init__(
        self,
        header: OemHeader,
        meta: OemMeta,
        states: list[tuple[datetime, np.ndarray]],
    ) -> None:
        self.header = header
        self.meta = meta
        self.states = states

    @classmethod
    def from_source(cls, source: Union[IO[str], str, Path]) -> CcsdsOem:
        raw_header, raw_meta, raw_states = read_oem(source)

        header = OemHeader(
            version=float(raw_header.get("CCSDS_OEM_VERS", 0.0)),
            comments=raw_header.get("COMMENT", []),
            creation_date=str(raw_header.get("CREATION_DATE", "")),
            originator=str(raw_header.get("ORIGINATOR", "")),
        )

        meta = OemMeta(
            object_name=str(raw_meta.get("OBJECT_NAME", "")),
            object_id=str(raw_meta.get("OBJECT_ID", "")),
            center_name=str(raw_meta.get("CENTER_NAME", "")),
            ref_frame=str(raw_meta.get("REF_FRAME", "")),
            time_system=str(raw_meta.get("TIME_SYSTEM", "")),
            start_time=str(raw_meta.get("START_TIME", "")),
            stop_time=str(raw_meta.get("STOP_TIME", "")),
            useable_start_time=str(raw_meta.get("USEABLE_START_TIME", "")),
            useable_stop_time=str(raw_meta.get("USEABLE_STOP_TIME", "")),
            interpolation=str(raw_meta.get("INTERPOLATION", "")),
            interpolation_degree=int(raw_meta.get("INTERPOLATION_DEGREE", 0)),
            comments=raw_meta.get("COMMENT", []),
        )

        state_list = [(epoch, sv) for epoch, sv in raw_states.items()]
        return cls(header=header, meta=meta, states=state_list)

    @property
    def epochs(self) -> list[datetime]:
        return [epoch for epoch, _ in self.states]

    @property
    def state_vectors(self) -> np.ndarray:
        return np.array([state for _, state in self.states])

    def to_file(self, dest: Union[IO[str], str, Path]) -> None:
        hdr = {
            "CCSDS_OEM_VERS": self.header.version,
            "CREATION_DATE": self.header.creation_date,
            "ORIGINATOR": self.header.originator,
        }
        if self.header.comments:
            hdr["COMMENT"] = self.header.comments

        mt: dict = {}
        if self.meta.comments:
            mt["COMMENT"] = self.meta.comments
        for key in _META_KEY_ORDER:
            attr = key.lower()
            val = getattr(self.meta, attr, None)
            if val is not None and val != "" and val != 0:
                mt[key] = val

        st = {epoch: state for epoch, state in self.states}
        write_oem(dest, hdr, mt, st)

    def __len__(self) -> int:
        return len(self.states)

    def __repr__(self) -> str:
        return (
            f"CcsdsOem(object={self.meta.object_name!r}, "
            f"frame={self.meta.ref_frame!r}, "
            f"epochs={len(self.states)})"
        )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m common.oem <oem_file>", file=sys.stderr)
        sys.exit(1)

    oem = CcsdsOem.from_source(Path(sys.argv[1]))
    print(oem)
    print(f"epochs: {len(oem)}")
