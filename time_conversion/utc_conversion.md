
| ISO-8601 converts to |  Conversions | Notes |
|----------------------|--------------|-------|
|ISO-8601            |       N/A
|POSIX               |utc_iso_to_utc_posix()
|Tudat UTC           |utc_iso_to_utc_tudat()
|Tudat TAI           |utc_iso_to_tai_tudat()
|Tudat TT            |utc_iso_to_tt_tudat()
|Tudat TDB           |utc_iso_to_tdb_tudat()
|chrono::sys_time    |utc_iso_to_sys_time()
|chrono::utc_time    |utc_iso_to_utc_time()
|chrono::tai_time    |utc_iso_to_tai_time()|


| POSIX converts to |  Conversions | Notes |
|----------------------|--------------|-------|
|ISO-8601            |utc_posix_to_utc_iso()
|POSIX               |N/A
|Tudat UTC           |utc_posix_to_utc_tudat()
|Tudat TAI           |utc_posix_to_tai_tudat()
|Tudat TT            |utc_posix_to_tt_tudat()
|Tudat TDB           |utc_posix_to_tdb_tudat()
|chrono::sys_time    |utc_posix_to_sys_time()
|chrono::utc_time    |utc_posix_to_utc_time()
|chrono::tai_time    |utc_posix_to_tai_time()


| Tudat UTC converts to |  Conversions | Notes |
|----------------------|--------------|-------|
|ISO-8601            |utc_tudat_to_utc_iso()
|POSIX               |utc_tudat_to_utc_posix()
|Tudat UTC           |N/A
|Tudat TAI           |utc_tudat_to_tai_tudat()
|Tudat TT            |utc_tudat_to_tt_tudat()
|Tudat TDB           |utc_tudat_to_tdb_tudat()
|chrono::sys_time    |utc_tudat_to_sys_time()
|chrono::utc_time    |utc_tudat_to_utc_time()|To test
|chrono::tai_time    |utc_tudat_to_tai_time()|To test

| Tudat TAI converts to |  Conversions | Notes |
|----------------------|--------------|-------|
|ISO-8601            |tai_tudat_to_utc_iso()
|POSIX               |tai_tudat_to_utc_posix()
|Tudat UTC           |tai_tudat_to_utc_tudat()
|Tudat TAI           |N/A
|Tudat TT            |tai_tudat_to_tt_tudat()
|Tudat TDB           |tai_tudat_to_tdb_tudat()
|chrono::sys_time    |tai_tudat_to_sys_time()|To do
|chrono::utc_time    |tai_tudat_to_utc_time()|To do
|chrono::tai_time    |tai_tudat_to_tai_time()|To do
