# tudatpy-utils

Utility scripts for working with TudatPy.

## Frame Conversion

### `frame_conversion/gcrf_to_itrf_spice.py`

Converts satellite state vectors (position and velocity) from the **GCRF** (Geocentric Celestial Reference Frame) to the **ITRF** (International Terrestrial Reference Frame) using SPICE rotation matrices via TudatPy.

#### Input Format

The script reads OEM-style ephemeris data with 7 whitespace- or comma-separated fields per line:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

- **Epoch**: ISO 8601 timestamp (e.g., `2025-11-10T15:42:27.000000`). A trailing `Z` is accepted and stripped.
- **Position**: X, Y, Z in **kilometres** (GCRF).
- **Velocity**: VX, VY, VZ in **km/s** (GCRF).

Lines that are blank or start with `#` are skipped.

#### Output Format

Each line of output contains the converted state in ITRF:

```
<ISO-8601 epoch>  <X_km>  <Y_km>  <Z_km>  <VX_km/s>  <VY_km/s>  <VZ_km/s>
```

Fields are separated by two spaces.

#### Usage

**From a file:**

```bash
python frame_conversion/gcrf_to_itrf_spice.py LEO_1MinInt_GCRF.txt
```

**From stdin (pipe):**

```bash
cat LEO_1MinInt_GCRF.txt | python frame_conversion/gcrf_to_itrf_spice.py
```

**Save output to a file:**

```bash
python frame_conversion/gcrf_to_itrf_spice.py LEO_1MinInt_GCRF.txt > LEO_1MinInt_ITRF_result.txt
```

#### Example

Given an input file `LEO_1MinInt_GCRF.txt`:

```
2025-11-10T15:42:27.000000   2.070058475322879e+03   4.729228905683604e+03   5.291073944519138e+03  -4.526864928985522e-01  -5.378340397167571e+00   4.970075197986098e+00
2025-11-10T15:43:27.000000   2.039244758072811e+03   4.398338130542555e+03   5.579702355150183e+03  -5.741321702569117e-01  -5.648088862971277e+00   4.648027399977921e+00
```

Running:

```bash
python frame_conversion/gcrf_to_itrf_spice.py LEO_1MinInt_GCRF.txt
```

Produces ITRF state vectors (position in km, velocity in km/s) for each epoch.

#### Dependencies

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

The script automatically loads the required SPICE kernels (`naif0012.tls` and `earth_200101_990825_predict.bpc`) from the TudatPy data directory.
