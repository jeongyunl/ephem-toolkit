# OEM to OPM Conversion

`oem-to-opm` fits an osculating two-body Keplerian orbit to a CCSDS OEM arc and writes a CCSDS Orbit Parameter Message (OPM). The output preserves the first OEM Cartesian state and includes the fitted Keplerian elements at that epoch.

## Usage

```bash
oem-to-opm [-h] -o <output_opm|-> [-v] [--mu <value>]
           [--fit-span <duration>] [--object-name <name>]
           [--object-id <YYYY-NNNP>] <input_oem|->
```

| Option | Description |
| --- | --- |
| `<input_oem>` | Input CCSDS OEM path. Use `-` to read from standard input. |
| `-o`, `--output` | Required output OPM path. Use `-` to write the OPM to standard output. |
| `-v`, `--verbose` | Write fitting diagnostics to standard error. |
| `--mu` | Gravitational parameter in m^3/s^2. Defaults to the Earth WGS-84 value. |
| `--fit-span` | Maximum fitting arc. Accepts durations such as `2h`, `90m`, or `3600s`; defaults to `2h`. |
| `--object-name` | Override `OBJECT_NAME` from the OEM metadata. |
| `--object-id` | Override `OBJECT_ID` from the OEM metadata. |

## Output

The OPM contains:

- Required OPM header and metadata fields, using OEM metadata where available.
- The first OEM Cartesian state as `EPOCH`, `X`, `Y`, `Z`, `X_DOT`, `Y_DOT`, and `Z_DOT`.
- Osculating `SEMI_MAJOR_AXIS`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `TRUE_ANOMALY`, and `GM` fields.

OPM Cartesian values are written in km and km/s. The fitted semi-major axis and gravitational parameter are written in km and km^3/s^2; angular elements are written in degrees.

## Fitting Method

The first OEM position is fixed at the OPM epoch. The command adjusts the epoch velocity with a damped Gauss-Newton fit to minimize Cartesian position residuals over the selected arc under two-body Kepler propagation. At least two OEM state vectors are required.

## Examples

Write an OPM file using OEM metadata:

```bash
oem-to-opm input.oem -o output.opm
```

Fit the first 90 minutes and override the object identifiers:

```bash
oem-to-opm --fit-span 90m --object-name ISS --object-id 1998-067A \
  input.oem -o iss.opm
```

Write an OPM to standard output from piped input:

```bash
cat input.oem | oem-to-opm - -o -
```

## Related Tools

- [`slice-oem`](SLICE_OEM.md) extracts a subset of an OEM arc or writes a single-state OPM.
- [`oem-to-omm`](OEM_TO_OMM.md) estimates mean-element OMM or TLE output from an OEM arc.
- [`propagate-kepler`](PROPAGATE_KEPLER.md) propagates Keplerian elements with a two-body model.