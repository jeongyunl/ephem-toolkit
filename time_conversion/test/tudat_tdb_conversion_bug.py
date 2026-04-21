#!/usr/bin/env python3

import tudatpy.astro.time_representation as time_representation
from tudatpy.astro.time_representation import DateTime, TimeScales

tudat_time_scale_converter = time_representation.default_time_scale_converter()

# FIXME Currently Tudat's TDB to UTC conversions fail for the second after end-of-June leap second insertions

for tt in [
    #
    -867931156.816,  # 1972-07-01 00:00:00
    -583934347.816,  # 1981-07-01 00:00:00
    -552398346.816,  # 1982-07-01 00:00:00
    -520862345.816,  # 1983-07-01 00:00:00
    -457703944.816,  # 1985-07-01 00:00:00
    -236779140.816,  # 1992-07-01 00:00:00
    -205243139.816,  # 1993-07-01 00:00:00
    -173707138.816,  # 1994-07-01 00:00:00
    -79012736.816,  # 1997-07-01 00:00:00
    394372867.184,  # 2012-07-01 00:00:00
    488980868.184 - 0.5,  # 2015-07-01 00:00:00
    488980868.184,  # 2015-07-01 00:00:00
    488980868.184 + 0.5,  # 2015-07-01 00:00:00
]:
    print(f"TT/TDB epoch: {tt}")

    utc_from_tt = tudat_time_scale_converter.convert_time(
        input_value=tt,
        input_scale=TimeScales.tt_scale,
        output_scale=TimeScales.utc_scale,
    )

    utc_from_tdb = tudat_time_scale_converter.convert_time(
        input_value=tt,
        input_scale=TimeScales.tdb_scale,
        output_scale=TimeScales.utc_scale,
    )

    if abs(utc_from_tt - utc_from_tdb) > 0.1:
        print("WARNING: UTC from TT and TDB differ by more than 0.1 seconds!")

        print(
            f"  UTC from TT:  {utc_from_tt:.3f} {DateTime.from_epoch(utc_from_tt).to_iso_string(number_of_digits_seconds=3)}"
        )
    print(
        f"  UTC from TDB: {utc_from_tdb:.3f} {DateTime.from_epoch(utc_from_tdb).to_iso_string(number_of_digits_seconds=3)}"
    )
    print()
