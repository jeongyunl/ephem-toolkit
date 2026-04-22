#pragma once

#include "convert_time_iso8601.h"

#include <string>

// Convert a parsed ISO-8601 UTC timestamp to seconds since the UTC J2000 epoch
// (2000-01-01 12:00:00 UTC), accounting for leap seconds.
//
// Notes:
// - This function does not use std::chrono.
// - Leap-second notation (..:59:60) is handled consistently with the rest of this library:
//   the leap second maps to the POSIX second of the following 00:00:00, but the leap transition
//   at that boundary is not counted yet.
// - Timezone offsets in ParsedUtcIso are applied (i.e., the input instant is converted to UTC).
//
// Returns: seconds (including fractional nanoseconds) since J2000 UTC.
double parsed_utc_iso_to_utc_j2000(const ParsedUtcIso& parsed_utc_iso);
double utc_iso_to_utc_j2000(const std::string& iso_string);

double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso);
double utc_iso_to_tai_j2000(const std::string& iso_string);

// Compares two ISO-8601 timestamps after parsing, allowing either 'T' or space between date/time.
// Fractional seconds are compared at the requested precision (0-9 decimal places) by truncation.
bool iso_8601_equal(const std::string& lhs, const std::string& rhs, std::size_t fractional_second_places = 3);
