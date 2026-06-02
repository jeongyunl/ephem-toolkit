# Base time-conversion map

This note summarizes the conversion relationships implemented by the standalone `base` backend under `time_conversion/base/`.

It is an internal implementation note for the base converter logic that underlies the `base` backend of `time_conversion/tools/convert_time_cli`.

> **Bold** indicates a direct conversion function.
> Non-bold indicates a conversion implemented through one or more intermediate conversions.

## Supported base-backend formats

The current `base` backend exposed by `convert_time_cli` supports:

- `iso`
- `posix`
- `utc`
- `tai`
- `tt`

Internally, this note uses the more explicit names:

- ISO-8601 UTC
- Parsed UTC ISO
- POSIX
- UTC J2000
- TAI J2000
- TT J2000

## Conversion graph

### ISO-8601 UTC to

- Parsed UTC ISO: **`utc_iso_to_parsed_utc_iso()`**
- POSIX: `utc_iso_to_posix()`
  - via `utc_iso_to_parsed_utc_iso()` + `parsed_utc_iso_to_posix()`
- UTC J2000: `utc_iso_to_utc_j2000()`
  - via `utc_iso_to_posix()` + `posix_to_utc_j2000()`
- TAI J2000: `utc_iso_to_tai_j2000()`
  - via `utc_iso_to_parsed_utc_iso()` + `parsed_utc_iso_to_tai_j2000()`
- TT J2000: `utc_iso_to_tt_j2000()`
  - via `utc_iso_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`

### Parsed UTC ISO to

- ISO-8601 UTC: **`parsed_utc_iso_to_utc_iso()`**
- POSIX: **`parsed_utc_iso_to_posix()`**
- UTC J2000: `parsed_utc_iso_to_utc_j2000()`
  - via `parsed_utc_iso_to_posix()` + `posix_to_utc_j2000()`
- TAI J2000: **`parsed_utc_iso_to_tai_j2000()`**
- TT J2000: `parsed_utc_iso_to_tt_j2000()`
  - via `parsed_utc_iso_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`

### POSIX to

- ISO-8601 UTC: `posix_to_utc_iso()`
  - via `posix_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- Parsed UTC ISO: **`posix_to_parsed_utc_iso()`**
- UTC J2000: **`posix_to_utc_j2000()`**
- TAI J2000: **`posix_to_tai_j2000()`**
- TT J2000: `posix_to_tt_j2000()`
  - via `posix_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`

### UTC J2000 to

- ISO-8601 UTC: `utc_j2000_to_utc_iso()`
  - via `utc_j2000_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- Parsed UTC ISO: `utc_j2000_to_parsed_utc_iso()`
  - via `utc_j2000_to_posix()` + `posix_to_parsed_utc_iso()`
- POSIX: **`utc_j2000_to_posix()`**
- TAI J2000: `utc_j2000_to_tai_j2000()`
  - via `utc_j2000_to_posix()` + `posix_to_tai_j2000()`
- TT J2000: `utc_j2000_to_tt_j2000()`
  - via `utc_j2000_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`

### TAI J2000 to

- ISO-8601 UTC: `tai_j2000_to_utc_iso()`
  - via `tai_j2000_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- Parsed UTC ISO: **`tai_j2000_to_parsed_utc_iso()`**
- POSIX: **`tai_j2000_to_posix()`**
- UTC J2000: `tai_j2000_to_utc_j2000()`
  - via `tai_j2000_to_posix()` + `posix_to_utc_j2000()`
- TT J2000: **`tai_j2000_to_tt_j2000()`**

### TT J2000 to

- ISO-8601 UTC: `tt_j2000_to_utc_iso()`
  - via `tt_j2000_to_tai_j2000()` + `tai_j2000_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- Parsed UTC ISO: `tt_j2000_to_parsed_utc_iso()`
  - via `tt_j2000_to_tai_j2000()` + `tai_j2000_to_parsed_utc_iso()`
- POSIX: `tt_j2000_to_posix()`
  - via `tt_j2000_to_tai_j2000()` + `tai_j2000_to_posix()`
- UTC J2000: `tt_j2000_to_utc_j2000()`
  - via `tt_j2000_to_posix()` + `posix_to_utc_j2000()`
- TAI J2000: **`tt_j2000_to_tai_j2000()`**
