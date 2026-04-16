#pragma once

#include <string>
#include <vector>

namespace convert_time_test
{
struct EpochRecord
{
	std::string iso;
	double posix;
	double utc;
	double tai;
	double tt;
	double tdb;
	double tdb_apx;
};

// Returns a cached view of the notable epochs dataset.
// NOTE: The cache is per-process and keyed only by the first provided path.
const std::vector<EpochRecord>& epoch_records();

bool is_leap_second_iso(const std::string& iso);

constexpr double kTolExactLike = 2.0e-4;
constexpr double kTolTimeScale = 2.0e-4;
constexpr double kTolTdb = 2.0e-4;
} // namespace convert_time_test
