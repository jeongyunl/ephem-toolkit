#include "convert_time.h"
#include "test/convert_time_common_gtest.h"

#include <gtest/gtest.h>
#include <tudat/interface/spice/spiceInterface.h>
#include <cmath>
#include <unordered_map>

namespace
{
using convert_time_test::EpochRecord;

bool has_ambiguous_posix(const double posix)
{
	static const auto posix_counts = [] {
		std::unordered_map<std::string, int> counts;
		for(const auto& record : convert_time_test::epoch_records())
		{
			const std::string key = std::to_string(record.posix);
			++counts[key];
		}
		return counts;
	}();

	const auto it = posix_counts.find(std::to_string(posix));
	return it != posix_counts.end() && it->second > 1;
}

class ConvertTimeDataDrivenTest : public ::testing::Test
{
protected:
	static void SetUpTestSuite()
	{
		tudat::spice_interface::loadSpiceKernelInTudat(tudat::paths::getSpiceKernelPath() + "/naif0012.tls");
	}
};

} // namespace

TEST_F(ConvertTimeDataDrivenTest, IsoToAllNumericScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(utc_iso_to_utc_posix(record.iso), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_iso_tudat_to_utc_tudat(record.iso), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_iso_tudat_to_tai_tudat(record.iso), record.tai, convert_time_test::kTolTimeScale)
			<< record.iso;
		EXPECT_NEAR(utc_iso_tudat_to_tt_tudat(record.iso), record.tt, convert_time_test::kTolTimeScale)
			<< record.iso;
		EXPECT_NEAR(utc_iso_tudat_to_tdb_tudat(record.iso), record.tdb, convert_time_test::kTolTdb)
			<< record.iso;
		EXPECT_NEAR(
			utc_iso_tudat_to_tdb_apx_tudat(record.iso),
			record.tdb_apx,
			convert_time_test::kTolTimeScale
		) << record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, PosixToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		EXPECT_NEAR(utc_posix_to_utc_tudat(record.posix), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_posix_to_tai_tudat(record.posix), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_posix_to_tt_tudat(record.posix), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_posix_to_tdb_tudat(record.posix), record.tdb, convert_time_test::kTolTdb)
			<< record.iso;
		EXPECT_NEAR(
			utc_posix_to_tdb_apx_tudat(record.posix),
			record.tdb_apx,
			convert_time_test::kTolExactLike
		) << record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, UtcToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		EXPECT_NEAR(utc_tudat_to_utc_posix(record.utc), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_tudat_to_tai_tudat(record.utc), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_tudat_to_tt_tudat(record.utc), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_tudat_to_tdb_tudat(record.utc), record.tdb, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(utc_tudat_to_tdb_apx_tudat(record.utc), record.tdb_apx, convert_time_test::kTolExactLike)
			<< record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, TaiToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tai_tudat_to_utc_posix(record.tai), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_tudat_to_utc_tudat(record.tai), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_tudat_to_tt_tudat(record.tai), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_tudat_to_tdb_tudat(record.tai), record.tdb, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tai_tudat_to_tdb_apx_tudat(record.tai), record.tdb_apx, convert_time_test::kTolExactLike)
			<< record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, TtToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tt_tudat_to_utc_posix(record.tt), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_tudat_to_utc_tudat(record.tt), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_tudat_to_tai_tudat(record.tt), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_tudat_to_tdb_tudat(record.tt), record.tdb, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tt_tudat_to_tdb_apx_tudat(record.tt), record.tdb_apx, convert_time_test::kTolExactLike)
			<< record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, TdbToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(!has_ambiguous_posix(record.posix))
		{
			EXPECT_NEAR(tdb_tudat_to_utc_posix(record.tdb), record.posix, convert_time_test::kTolTdb)
				<< record.iso;
			EXPECT_NEAR(tdb_tudat_to_utc_tudat(record.tdb), record.utc, convert_time_test::kTolTdb)
				<< record.iso;
		}

		EXPECT_NEAR(tdb_tudat_to_tai_tudat(record.tdb), record.tai, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_tudat_to_tt_tudat(record.tdb), record.tt, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_tudat_to_tdb_apx_tudat(record.tdb), record.tdb_apx, convert_time_test::kTolTdb)
			<< record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, TdbApproxToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(
			tdb_apx_tudat_to_utc_posix(record.tdb_apx),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;
		EXPECT_NEAR(tdb_apx_tudat_to_utc_tudat(record.tdb_apx), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tdb_apx_tudat_to_tai_tudat(record.tdb_apx), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tdb_apx_tudat_to_tt_tudat(record.tdb_apx), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tdb_apx_tudat_to_tdb_tudat(record.tdb_apx), record.tdb, convert_time_test::kTolTdb)
			<< record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, UtcIsoIdentityRoundTripForRecords)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_EQ(utc_iso_tudat_to_utc_iso_tudat(record.iso), record.iso);
	}
}

TEST_F(ConvertTimeDataDrivenTest, NumericRoundTripUsingUtcIsStableForNonLeapSecondRows)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		const double utc_from_posix = utc_posix_to_utc_tudat(record.posix);
		const double posix_from_utc = utc_tudat_to_utc_posix(utc_from_posix);
		EXPECT_NEAR(posix_from_utc, record.posix, convert_time_test::kTolExactLike) << record.iso;

		const double tai_from_utc = utc_tudat_to_tai_tudat(record.utc);
		const double utc_from_tai = tai_tudat_to_utc_tudat(tai_from_utc);
		EXPECT_NEAR(utc_from_tai, record.utc, convert_time_test::kTolExactLike) << record.iso;
	}
}
