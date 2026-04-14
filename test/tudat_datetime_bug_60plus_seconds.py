#!/usr/bin/env python3

from tudatpy.astro.time_representation import DateTime


try:
    # FIXME: This should be valid, but currently raises an error in Tudat
    dt_2016_12_31_23_59_60_5 = DateTime.from_iso_string("2016-12-31 23:59:60.5")
    print(dt_2016_12_31_23_59_60_5.to_epoch())
except RuntimeError as e:
    print(f"Error parsing leap second: {e}")
