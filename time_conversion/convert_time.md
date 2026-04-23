
> **Bold** indicates direct conversions.
Non-bold indicates conversions that are implemented via one or more intermediate conversions.

ISO-8601 Time to
- ParsedUtcIso: **`utc_iso_to_parsed_utc_iso()`**
- POSIX Time: `utc_iso_to_posix()`
  - via `utc_iso_to_parsed_utc_iso()` + `parsed_utc_iso_to_posix()`
- UTC J2000 Time: `utc_iso_to_utc_j2000()`
  - via `utc_iso_to_parsed_utc_iso()` + `parsed_utc_iso_to_posix()` + `posix_to_utc_j2000()`
- TAI J2000 Time: `utc_iso_to_tai_j2000()`
  - via `utc_iso_to_parsed_utc_iso()` + `parsed_utc_iso_to_tai_j2000()`
- TT J2000 Time: `utc_iso_to_tt_j2000()`
  - via `utc_iso_to_parsed_utc_iso()` + `parsed_utc_iso_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`
<br>

ParsedUtcIso Time to
- ISO-8601: **`parsed_utc_iso_to_utc_iso()`**
- POSIX Time: **`parsed_utc_iso_to_posix()`**
- UTC J2000 Time: `parsed_utc_iso_to_utc_j2000()`
  - via `parsed_utc_iso_to_posix()` + `posix_to_utc_j2000()`
- TAI J2000 Time: **`parsed_utc_iso_to_tai_j2000()`**
- TT J2000 Time: `parsed_utc_iso_to_tt_j2000()`
  - via `parsed_utc_iso_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`
<br>

POSIX Time to
- ISO-8601: `posix_to_utc_iso()`
  - via `posix_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- ParsedUtcIso: **`posix_to_parsed_utc_iso()`**
- UTC J2000 Time: **`posix_to_utc_j2000()`**
- TAI J2000 Time: **`posix_to_tai_j2000()`**
- TT J2000 Time: `posix_to_tt_j2000()`
  - via `posix_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`
<br>

UTC J2000 Time to
- ISO-8601: `utc_j2000_to_utc_iso()`
  - via `utc_j2000_to_posix()` + `posix_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- ParsedUtcIso: `utc_j2000_to_parsed_utc_iso()` 
  - via `utc_j2000_to_posix()` + `posix_to_parsed_utc_iso()`
- POSIX Time: **`utc_j2000_to_posix()`**
- TAI J2000 Time: `utc_j2000_to_tai_j2000()` 
  - via `utc_j2000_to_posix()` + `posix_to_tai_j2000()`
- TT J2000 Time: `utc_j2000_to_tt_j2000()`
  - via `utc_j2000_to_posix()` + `posix_to_tai_j2000()` + `tai_j2000_to_tt_j2000()`
<br>

TAI J2000 Time to
- ISO-8601: `tai_j2000_to_utc_iso()`
  - via `tai_j2000_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- ParsedUtcIso: **`tai_j2000_to_parsed_utc_iso()`**
- POSIX Time: **`tai_j2000_to_posix()`**
- UTC J2000 Time: `tai_j2000_to_utc_j2000()` 
  - via `tai_j2000_to_posix()` + `posix_to_utc_j2000()`
- TT J2000 Time: **`tai_j2000_to_tt_j2000()`**
<br>

TT J2000 Time to
- ISO-8601: `tt_j2000_to_utc_iso()`
  - via `tt_j2000_to_tai_j2000()` + `tai_j2000_to_parsed_utc_iso()` + `parsed_utc_iso_to_utc_iso()`
- ParsedUtcIso: `tt_j2000_to_parsed_utc_iso()`
  - via `tt_j2000_to_tai_j2000()` + `tai_j2000_to_parsed_utc_iso()`
- POSIX Time: `tt_j2000_to_posix()`
  - via `tt_j2000_to_tai_j2000()` + `tai_j2000_to_posix()`
- UTC J2000 Time: `tt_j2000_to_utc_j2000()`
  - via `tt_j2000_to_tai_j2000()` + `tai_j2000_to_posix()` + `posix_to_utc_j2000()`
- TAI J2000 Time: **`tt_j2000_to_tai_j2000()`**