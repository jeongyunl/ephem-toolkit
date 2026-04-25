#!/usr/bin/env python3

from datetime import datetime, timezone
from tudatpy.astro.time_representation import DateTime

py_datetime = (
    DateTime.from_iso_string("2016-12-31 23:59:60.0")
    .to_python_datetime()
    .replace(tzinfo=timezone.utc)
)

print("2016-12-31 23:59:60.0", py_datetime, py_datetime.timestamp())

# FIXME DateTime.to_python_datetime() has a bug where it does not handle seconds >= 60 correctly
assert (
    py_datetime.timestamp() == 1483228800.0
), f"Expected POSIX timestamp 1483228800.0 for 2016-12-31 23:59:60 UTC, got {py_datetime.timestamp()}"
