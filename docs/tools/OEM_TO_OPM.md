# OEM to OPM Conversion

`oem-to-opm` fits an osculating two-body Keplerian orbit to a CCSDS OEM arc and writes a CCSDS Orbit Parameter Message (OPM). The output preserves the first OEM Cartesian state and includes the fitted Keplerian elements at that epoch.

## Usage

```bash
oem-to-opm [-h] -o <output_opm|-> [-v] [--mu <value>]
           [--fit-span <duration>] [--fit-model <two-body|numerical>]
           [--object-name <name>] [--object-id <YYYY-NNNP>]
           [--fit-report <path|->] [--no-fit-report]
           [--source-model <name>] [--source-report <path>]
           [--fit-position-weight <value>] [--fit-end-weight <value>]
           [--fit-max-iterations <count>] [--fit-stagnation-tries <count>]
           [--fit-parameters <selection>] [--mass <kg>] [--drag-area <m2>]
           [--drag <on|off>] [--drag-coeff <value>]
           [--srp <on|off>] [--srp-coeff <value>] <input_oem|->
```

| Option | Description |
| --- | --- |
| `<input_oem>` | Input CCSDS OEM path. Use `-` to read from standard input. |
| `-o`, `--output` | Required output OPM path. Use `-` to write the OPM to standard output. |
| `-v`, `--verbose` | Write fitting diagnostics to standard error. `--debug` enables more detailed diagnostics and implies verbose output. |
| `--mu` | Gravitational parameter in m^3/s^2 for the two-body fit and its output `GM`. Defaults to the Earth WGS-84 value. It does not configure the numerical force model. |
| `--fit-span` | Maximum fitting arc measured from the first OEM epoch. Accepts durations such as `4h`, `90m`, or `3600s`; defaults to `4h`. At least two states must fall within the span. |
| `--fit-model` | Fit model: `two-body` (default) or `numerical`. |
| `--object-name` | Override `OBJECT_NAME`; otherwise use OEM metadata, falling back to `OBJECT`. |
| `--object-id` | Override `OBJECT_ID`; otherwise use OEM metadata, falling back to `UNKNOWN`. |
| `--fit-report <path|->` | Write JSON fit diagnostics to a path or standard output. By default a report is created automatically; see [Fit Reports](#fit-reports). |
| `--no-fit-report` | Disable automatic fit-report creation. Cannot be combined with `--fit-report`. |
| `--source-model` | Set the input provenance model recorded in the OPM and fit report. Defaults to `auto`, which uses the source report when available and otherwise records `unknown`. |
| `--source-report <path>` | Read a JSON source provenance report. |
| `--fit-position-weight <value>` | Numerical mode position-residual scaling parameter; defaults to `1.0`. |
| `--fit-end-weight <value>` | Numerical mode multiplier applied toward the end of the fit span; defaults to `2.0`. |
| `--fit-max-iterations <count>` | Numerical mode maximum optimizer iterations; defaults to `100`. |
| `--fit-stagnation-tries <count>` | Numerical mode additional worsening or stagnant tries before stopping; defaults to `3`. |
| `--fit-parameters` | Numerical mode parameter selection: `initial-state` (default), `initial-state,drag-coeff`, or `initial-state,srp-coeff`. |
| `--mass <kg>` | Numerical mode spacecraft mass; defaults to `30 kg`. |
| `--drag-area <m2>` | Numerical mode drag/SRP reference area; defaults to `0.18 m^2`. |
| `--drag <on|off>` / `--drag-coeff <value>` | Enable or disable drag (default `on`) and set its coefficient (default `2.2`) in numerical mode. |
| `--srp <on|off>` / `--srp-coeff <value>` | Enable or disable solar radiation pressure (default `on`) and set its coefficient (default `1.2`) in numerical mode. |

The numerical fit also uses the project's configured numerical propagator defaults, including Earth gravity and third-body gravity. The force-model and spacecraft options above apply only when `--fit-model numerical` is selected.

## Output

Both modes write the required OPM header, metadata, and Cartesian state-vector fields. Missing OEM metadata uses these defaults: `CENTER_NAME=EARTH`, `REF_FRAME=ICRF`, and `TIME_SYSTEM=UTC`. The OPM also includes source and fit-summary comments.

With the default `--fit-model two-body`, the OPM contains:

- The first OEM Cartesian state as `EPOCH`, `X`, `Y`, `Z`, `X_DOT`, `Y_DOT`, and `Z_DOT`.
- Osculating `SEMI_MAJOR_AXIS`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`, `ARG_OF_PERICENTER`, `TRUE_ANOMALY`, and `GM` fields.

With `--fit-model numerical`, the OPM contains the fitted Cartesian state at the first OEM epoch. Its position is held at the first OEM position while the velocity is fit; no Keplerian element block or `GM` field is written.

OPM Cartesian values are written in km and km/s. The fitted semi-major axis and gravitational parameter are written in km and km^3/s^2; angular elements are written in degrees.

## Fitting Method

The fit uses OEM records from the first epoch through the selected maximum span and minimizes position residuals; OEM velocities are not fit residuals. In two-body mode, the first OEM position is fixed and a damped Gauss-Newton fit adjusts the epoch velocity under two-body Kepler propagation. The OPM Cartesian state remains the original first OEM state; the adjusted velocity is represented by the fitted Keplerian elements. At least two OEM state vectors must be available in the fitting span.

Numerical mode fits the epoch Cartesian state using the configured numerical propagator. The first position remains fixed, while the epoch velocity is adjusted. Drag and solar radiation pressure are enabled by default; use their corresponding options to change the force model. Numerical mode is more computationally expensive than the default two-body fit.

## Fit Reports

Unless disabled with `--no-fit-report`, the command writes a JSON fit report alongside the output OPM, replacing its extension with `.fit.json` (for example, `output.opm` produces `output.fit.json`). If the OPM is written to standard output and the OEM input is a file, the report is derived from the input filename instead. When both input and OPM use standard input/output, no report is created automatically. Use `--fit-report` to choose an explicit report destination. Do not direct both the OPM and its JSON report to standard output in the same invocation.

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