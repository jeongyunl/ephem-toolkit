# ephem-toolkit

Command-line tools for processing, converting, propagating, comparing, and visualizing OEM, OPM, OMM, and TLE ephemeris data with TudatPy and Tudat.

## Overview

This project provides a practical toolkit for working with ephemerides and related astrodynamics data. Built on top of [TudatPy](https://docs.tudat.space/en/latest/) and [Tudat](https://docs.tudat.space/), it includes a focused set of command-line tools for ingesting, transforming, comparing, propagating, and plotting CCSDS OEM, OPM, OMM, and TLE data.

The toolkit supports workflows for working with ephemeris products: parse OEM, OMM, and TLE inputs, fit or convert mean elements, propagate trajectories, compare results, and visualize dependent variables and orbit differences.

The propagation commands cover numerical Cartesian propagation (`propagate-orbit`), two-body Kepler propagation from OPM elements (`propagate-kepler`), and model-selected mean-element propagation (`propagate-omm` and `propagate-tle`).

### OEM file data flow

```mermaid
flowchart LR
    fmt_oem{{"OEM / State Vectors <br/> (CCSDS OEM or simple format: epoch x y z vx vy vz)"}}
    fmt_opm{{"OPM (.opm) <br/> Cartesian-only or Cartesian + osculating Keplerian elements"}}
    fmt_omm{{"OMM (.omm)"}}
    fmt_tle{{"TLE (.tle)"}}
    fmt_dep_vars_csv{{"Dependent Variables CSV"}}
    fmt_plots{{"Plots / Animations <br/> (Matplotlib figures)"}}
    fmt_raw_states{{"Raw Cartesian state lines <br/> (epoch x y z vx vy vz)"}}
    fmt_aer{{"AER text <br/> (stdout)"}}

    oem_to_omm(["oem-to-omm"])
    oem_to_tle(["oem-to-tle"])
    oem_to_opm(["oem-to-opm"])
    propagate_sat(["propagate-orbit"])
    propagate_kepler(["propagate-kepler"])
    propagate_omm(["propagate-omm"])
    plot_oem(["plot-oem"])
    plot_oem_diff(["plot-oem-diff"])
    plot_dep_vars(["plot-dependent-variables"])
    diff_oem(["diff-oem"])
    slice_oem(["slice-oem"])
    xform_oem(["xform-oem"])

    fmt_oem --> oem_to_omm
    oem_to_omm --> fmt_omm
    fmt_oem --> oem_to_tle
    oem_to_tle -->|"SGP4 TLE (via intermediate OMM)"| fmt_tle
    fmt_oem --> oem_to_opm
    oem_to_opm --> fmt_opm

    fmt_opm -->|"Cartesian initial state"| propagate_sat
    propagate_sat -->|"state history"| fmt_oem
    propagate_sat -->|"--dep-vars (optional)"| fmt_dep_vars_csv

    fmt_opm -->|"complete osculating Keplerian element set"| propagate_kepler
    propagate_kepler --> fmt_oem

    fmt_omm -->|"OMM input"| propagate_omm
    propagate_omm --> fmt_oem

    fmt_oem -->|"two files: reference + comparison"| diff_oem
    fmt_oem --> plot_oem
    fmt_oem -->|"reference + optional comparisons"| plot_oem_diff
    plot_oem --> fmt_plots
    plot_oem_diff --> fmt_plots

    fmt_dep_vars_csv --> plot_dep_vars
    plot_dep_vars --> fmt_plots

    fmt_oem --> slice_oem
    slice_oem -->|"OEM output"| fmt_oem
    slice_oem -->|"--data-only"| fmt_raw_states
    slice_oem -->|"Cartesian-only single-state OPM"| fmt_opm

    fmt_oem -->|"source frame + target frame"| xform_oem
    xform_oem -->|"converted OEM"| fmt_oem
    xform_oem -->|"AER text"| fmt_aer
```

### OPM/OMM/TLE file data flow

```mermaid
flowchart LR
    fmt_tle{{"TLE (.tle)"}}
    fmt_opm{{"OPM (.opm) <br/> Cartesian-only or Cartesian + osculating Keplerian elements"}}
    fmt_omm{{"OMM (.omm)"}}
    fmt_oem{{"OEM / State Vectors <br/> (CCSDS OEM or simple format: epoch x y z vx vy vz)"}}

    download_tle(["download-tle"])
    omm_to_tle(["omm-to-tle"])
    tle_to_omm(["tle-to-omm"])
    tle_info(["tle-info"])
    oem_to_omm(["oem-to-omm"])
    oem_to_tle(["oem-to-tle"])
    oem_to_opm(["oem-to-opm"])
    omm_to_opm(["omm-to-opm"])
    tle_to_opm(["tle-to-opm"])
    fmt_text_report{{"TLE summary / fitting report <br/> (stdout or file)"}}
    propagate_tle(["propagate-tle"])
    propagate_omm(["propagate-omm"])
    propagate_kepler(["propagate-kepler"])

    fmt_tle --> tle_to_omm
    tle_to_omm --> fmt_omm

    fmt_omm --> omm_to_tle
    omm_to_tle --> fmt_tle

    fmt_tle --> tle_info
    tle_info -->|"epoch, state, osculating elements"| fmt_text_report

    fmt_oem --> oem_to_omm
    oem_to_omm --> fmt_omm
    fmt_oem -->|"Cartesian state history"| oem_to_tle
    oem_to_tle -->|"SGP4 TLE via intermediate OMM"| fmt_tle
    fmt_oem -->|"Cartesian state history"| oem_to_opm
    oem_to_opm --> fmt_opm

    fmt_tle --> propagate_tle
    propagate_tle --> fmt_oem

    fmt_omm --> propagate_omm
    propagate_omm --> fmt_oem
    fmt_omm -->|"declared mean-element model"| omm_to_opm
    omm_to_opm -->|"reference arc propagation + numerical fit"| fmt_opm
    fmt_tle -->|"SGP4 reference arc"| tle_to_opm
    tle_to_opm -->|"reference arc propagation + numerical fit"| fmt_opm

    fmt_opm -->|"complete osculating Keplerian element set"| propagate_kepler
    propagate_kepler --> fmt_oem

    download_tle -->|"default format: TLE"| fmt_tle
    download_tle -->|"--format omm"| fmt_omm
```

---

## Command-Line Tools


### Command groups

#### OEM utilities

| Workflow | Command |
| --- | --- |
| OEM comparison | [`diff-oem`](docs/DIFF_OEM.md) |
| OEM slicing | [`slice-oem`](docs/SLICE_OEM.md) |
| OEM frame/coordinate transformation | [`xform-oem`](docs/XFORM_OEM.md) |
| OEM to OPM fitting | [`oem-to-opm`](docs/OEM_TO_OPM.md) |
| OEM to OMM fitting | [`oem-to-omm`](docs/OEM_TO_OMM.md) |
| OEM to TLE fitting | [`oem-to-tle`](docs/ORBIT_FILE_CONVERSION.md) |

#### Orbit propagation

| Workflow | Command |
| --- | --- |
| Numerical orbit propagation | [`propagate-orbit`](docs/PROPAGATE_ORBIT.md) |
| Mean Keplerian orbit propagation | [`propagate-omm`](docs/PROPAGATE_OMM.md) |
| DSST semi-analytical propagation | [`propagate-omm`](docs/PROPAGATE_DSST.md) (via `MEAN_ELEMENT_THEORY = DSST`) |
| Kepler propagation | [`propagate-kepler`](docs/PROPAGATE_KEPLER.md) |
| TLE propagation | [`propagate-tle`](docs/PROPAGATE_TLE.md) |

#### TLE / OMM utilities

| Workflow | Command |
| --- | --- |
| TLE download | [`download-tle`](docs/DOWNLOAD_TLE.md) |
| OMM to TLE | [`omm-to-tle`](docs/OMM_TO_TLE.md) |
| TLE inspection | [`tle-info`](docs/TLE_INFO.md) |
| TLE to OMM | [`tle-to-omm`](docs/TLE_TO_OMM.md) |
| OMM to OPM fitting | [`omm-to-opm`](docs/ORBIT_FILE_CONVERSION.md) |
| TLE to OPM fitting | [`tle-to-opm`](docs/ORBIT_FILE_CONVERSION.md) |

#### Plotting and analysis

| Workflow | Command |
| --- | --- |
| Orbit plotting | [`plot-oem`](docs/PLOT_OEM.md) |
| Orbit-delta plotting | [`plot-oem-diff`](docs/PLOT_OEM_DIFF.md) |
| Dependent-variable plotting | [`plot-dependent-variables`](docs/PLOT_DEPENDENT_VARIABLES.md) |


TudatPy-dependent workflows require TudatPy and its transitive dependencies through an external installation method.

### OEM Utilities

- [`diff-oem`](docs/DIFF_OEM.md) — compare corresponding states from two OEM files with optional rotation fitting and time-shift correction.
- [`slice-oem`](docs/SLICE_OEM.md) — slice OEM files by index or time range (with optional interpolation).
- [`xform-oem`](docs/XFORM_OEM.md) — transform OEM state vectors between supported reference frames and convert ECEF positions to AER coordinates.


### Orbit Propagation

- [`propagate-orbit`](docs/PROPAGATE_ORBIT.md) — numerical orbit propagation with configurable perturbations and Cartesian state integration
- [`propagate-omm`](docs/PROPAGATE_OMM.md) — propagate OMM elements to OEM output using SGP4 or DSST where supported; other non-TLE theories use a labeled two-body Kepler fallback
- [`propagate-kepler`](docs/PROPAGATE_KEPLER.md) — two-body Kepler propagation
- [`propagate-tle`](docs/PROPAGATE_TLE.md) — SGP4 TLE propagation

Supports CCSDS OEM export, data-only state-vector output, dependent-variable CSV export, and OEM metadata headers.

### OEM-to-OMM

- [`oem-to-omm`](docs/OEM_TO_OMM.md)

Fits OEM Cartesian state histories to mean-element models and writes a CCSDS OMM. Supported fit models are Brouwer, DSST, and SGP4. Use `oem-to-tle` for TLE output; it fits through an intermediate OMM and then formats the TLE.

### OEM-to-OPM

- [`oem-to-opm`](docs/OEM_TO_OPM.md)

Fits an OEM arc and writes an OPM using either a two-body osculating fit or a numerical fit. Both modes write a Cartesian state; the two-body mode also writes fitted Keplerian elements.

### TLE / OMM Utilities

- [`download-tle`](docs/DOWNLOAD_TLE.md) — download CelesTrak GP data in a selected format, including TLE and OMM
- [`omm-to-tle`](docs/OMM_TO_TLE.md) — convert OMM → TLE
- [`tle-to-omm`](docs/TLE_TO_OMM.md) — convert TLE → OMM
- [`tle-info`](docs/TLE_INFO.md) — inspect TLE information
- [`omm-to-opm`](docs/ORBIT_FILE_CONVERSION.md) — propagate OMM elements and numerically fit an OPM state
- [`tle-to-opm`](docs/ORBIT_FILE_CONVERSION.md) — propagate a TLE with SGP4 and numerically fit an OPM state

### Visualization

- [`plot-oem`](docs/PLOT_OEM.md) — visualize orbit trajectories and output state histories
- [`plot-oem-diff`](docs/PLOT_OEM_DIFF.md) — plot and compare multiple orbits
- [`plot-dependent-variables`](docs/PLOT_DEPENDENT_VARIABLES.md) — plot dependent variables from propagation output

---

## Libraries

### Python Library (`src/ephem_toolkit/core/`)

Reusable Python modules providing foundational astrodynamics functionality. These are imported by the application modules and CLI tools.

**Key modules:**
- **Interpolation** — Hermite, Chebyshev, and Lagrange polynomial interpolators with configurable degree
- **CCSDS** — OEM, OPM, OMM, and ODM parsers and writers
- **Time utilities** — ISO 8601, duration parsing, time conversions
- **Orbital elements** — Cartesian ↔ Keplerian conversions, anomaly calculations
- **Coordinate transformations** — Frame conversions, WGS-84, AER coordinates
- **TLE utilities** — TLE parsing, validation, and conversions

See [CORE_LIBRARY_SUMMARY.md](docs/CORE_LIBRARY_SUMMARY.md) for an overview of all available modules and functions.

---

## Repository Layout

```
src/
├── ephem_toolkit/
│   ├── core/                 Shared astrodynamics and time utilities
│   │   ├── ccsds/            CCSDS ODM, OEM, OPM, and OMM models and parsers
│   │   ├── interpolator/     Lagrange, Hermite, and Chebyshev interpolation
│   │   ├── propagator/       Kepler, Brouwer, DSST, numerical, and SGP4 models
│   │   └── ...               Coordinate, time, and orbital-element modules
│   ├── diff_oem/             OEM comparison
│   ├── download_tle/         CelesTrak GP data download
│   ├── oem_to_omm/           OEM mean-element fitting
│   ├── oem_to_opm/           OEM-to-OPM two-body and numerical fitting
│   ├── oem_to_tle/           OEM-to-TLE fitting wrapper
│   ├── omm_to_opm/           OMM-to-OPM numerical fitting wrapper
│   ├── omm_to_tle/           OMM-to-TLE conversion
│   ├── plot_dep_vars/        Dependent-variable plotting
│   ├── plot_oem/             Orbit visualization
│   ├── plot_oem_diff/        Orbit-difference plotting
│   ├── propagate_kepler/     Two-body Kepler propagation
│   ├── propagate_omm/        OMM and TLE propagation
│   ├── propagate_orbit/      Numerical Cartesian propagation
│   ├── propagate_tle/        TLE propagation wrapper
│   ├── slice_oem/            OEM slicing
│   ├── tle_info/             TLE inspection
│   ├── tle_to_omm/           TLE-to-OMM conversion
│   ├── tle_to_opm/           TLE-to-OPM numerical fitting wrapper
│   └── xform_oem/            OEM frame transformation
└── ...                     Other project source modules

tests/                      Unit tests and sample data files
docs/                       Documentation
README.md                   Project overview and usage guide
pyproject.toml              Project configuration and dependencies
```


## Build and Dependencies

### Python Tools

Typical Python dependencies used by the scripts:

- [TudatPy](https://docs.tudat.space/en/latest/) (`tudatpy`)
- NumPy

Some scripts use only the Python standard library plus local helpers.
