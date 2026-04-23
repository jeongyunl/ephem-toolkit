#pragma once

#include <cstdint>
#include <vector>

struct LeapTransition
{
	std::int64_t transition_posix_epoch;
	int correction_seconds;
};

const std::vector<LeapTransition>& get_zoneinfo_leap_transitions();

// Returns TAI minus UTC, in seconds, at the supplied UTC POSIX epoch.
// For UTC before 1972-01-01, this uses the historical linear pre-1972 model.
// For UTC on or after 1972-01-01, this starts from 10.0 s and adds leap-second
// corrections for transitions strictly before posix_time. If
// include_transition_at_equal is true, a transition exactly at posix_time
// is also included.
double cumulative_leap_correction(
	const std::vector<LeapTransition>& transitions,
	double posix_time,
	bool include_transition_at_equal
);
