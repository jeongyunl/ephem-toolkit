#include "convert_time.h"

#include <gtest/gtest.h>

#include <cmath>
#include <fstream>
#include <unordered_map>
#include <sstream>
#include <string>
#include <vector>

#include <tudat/interface/spice/spiceInterface.h>

namespace
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

std::vector<std::string> split_tab(const std::string& line)
{
    std::vector<std::string> fields;
    std::stringstream stream(line);
    std::string token;

    while(std::getline(stream, token, '\t'))
    {
        fields.push_back(token);
    }

    return fields;
}

std::vector<EpochRecord> load_epoch_records(const std::string& path)
{
    std::ifstream input(path);
    if(!input.is_open())
    {
        throw std::runtime_error("Failed to open notable epochs data file: " + path);
    }

    std::vector<EpochRecord> records;
    std::string line;

    if(!std::getline(input, line))
    {
        throw std::runtime_error("Notable epochs data file is empty: " + path);
    }

    while(std::getline(input, line))
    {
        if(line.empty())
        {
            continue;
        }

        const auto fields = split_tab(line);
        if(fields.size() != 7)
        {
            throw std::runtime_error("Unexpected column count in notable epochs line: " + line);
        }

        records.push_back(
            EpochRecord{
                fields[0],
                std::stod(fields[1]),
                std::stod(fields[2]),
                std::stod(fields[3]),
                std::stod(fields[4]),
                std::stod(fields[5]),
                std::stod(fields[6])
            }
        );
    }

    return records;
}

const std::vector<EpochRecord>& epoch_records()
{
    static const auto records = load_epoch_records(NOTABLE_EPOCHS_FILE);
    return records;
}

bool is_leap_second_iso(const std::string& iso)
{
    return iso.find(":60") != std::string::npos;
}

bool has_ambiguous_posix(const double posix)
{
    static const auto posix_counts = [] {
        std::unordered_map<std::string, int> counts;
        for(const auto& record : epoch_records())
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
        tudat::spice_interface::loadSpiceKernelInTudat(
            tudat::paths::getSpiceKernelPath() + "/naif0012.tls"
        );
    }
};

constexpr double kTolExactLike = 2.0e-4;
constexpr double kTolTimeScale = 2.0e-4;
constexpr double kTolTdb = 2.0e-4;
}

TEST_F(ConvertTimeDataDrivenTest, IsoToAllNumericScalesMatchReferenceData)
{
    for(const auto& record : epoch_records())
    {
        EXPECT_NEAR(utc_iso_tudat_to_utc_posix(record.iso), record.posix, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_iso_tudat_to_utc_tudat(record.iso), record.utc, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_iso_tudat_to_tai_tudat(record.iso), record.tai, kTolTimeScale) << record.iso;
        EXPECT_NEAR(utc_iso_tudat_to_tt_tudat(record.iso), record.tt, kTolTimeScale) << record.iso;
        EXPECT_NEAR(utc_iso_tudat_to_tdb_tudat(record.iso), record.tdb, kTolTdb) << record.iso;
        EXPECT_NEAR(utc_iso_tudat_to_tdb_apx_tudat(record.iso), record.tdb_apx, kTolTimeScale)
            << record.iso;
    }
}

TEST_F(ConvertTimeDataDrivenTest, PosixToOtherScalesMatchReferenceData)
{
    for(const auto& record : epoch_records())
    {
        if(is_leap_second_iso(record.iso))
        {
            continue;
        }

        EXPECT_NEAR(utc_posix_to_utc_tudat(record.posix), record.utc, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_posix_to_tai_tudat(record.posix), record.tai, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_posix_to_tt_tudat(record.posix), record.tt, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_posix_to_tdb_tudat(record.posix), record.tdb, kTolTdb) << record.iso;
        EXPECT_NEAR(utc_posix_to_tdb_apx_tudat(record.posix), record.tdb_apx, kTolExactLike)
            << record.iso;
    }
}

TEST_F(ConvertTimeDataDrivenTest, UtcToOtherScalesMatchReferenceData)
{
    for(const auto& record : epoch_records())
    {
        if(is_leap_second_iso(record.iso))
        {
            continue;
        }

        EXPECT_NEAR(utc_tudat_to_utc_posix(record.utc), record.posix, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_tudat_to_tai_tudat(record.utc), record.tai, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_tudat_to_tt_tudat(record.utc), record.tt, kTolExactLike) << record.iso;
        EXPECT_NEAR(utc_tudat_to_tdb_tudat(record.utc), record.tdb, kTolTdb) << record.iso;
        EXPECT_NEAR(utc_tudat_to_tdb_apx_tudat(record.utc), record.tdb_apx, kTolExactLike)
            << record.iso;
    }
}

TEST_F(ConvertTimeDataDrivenTest, TaiToOtherScalesMatchReferenceData)
{
    for(const auto& record : epoch_records())
    {
        EXPECT_NEAR(tai_tudat_to_utc_posix(record.tai), record.posix, kTolExactLike) << record.iso;
        EXPECT_NEAR(tai_tudat_to_utc_tudat(record.tai), record.utc, kTolExactLike) << record.iso;
        EXPECT_NEAR(tai_tudat_to_tt_tudat(record.tai), record.tt, kTolExactLike) << record.iso;
        EXPECT_NEAR(tai_tudat_to_tdb_tudat(record.tai), record.tdb, kTolTdb) << record.iso;
        EXPECT_NEAR(tai_tudat_to_tdb_apx_tudat(record.tai), record.tdb_apx, kTolExactLike) << record.iso;
    }
}

TEST_F(ConvertTimeDataDrivenTest, TtToOtherScalesMatchReferenceData)
{
    for(const auto& record : epoch_records())
    {
        EXPECT_NEAR(tt_tudat_to_utc_posix(record.tt), record.posix, kTolExactLike) << record.iso;
        EXPECT_NEAR(tt_tudat_to_utc_tudat(record.tt), record.utc, kTolExactLike) << record.iso;
        EXPECT_NEAR(tt_tudat_to_tai_tudat(record.tt), record.tai, kTolExactLike) << record.iso;
        EXPECT_NEAR(tt_tudat_to_tdb_tudat(record.tt), record.tdb, kTolTdb) << record.iso;
        EXPECT_NEAR(tt_tudat_to_tdb_apx_tudat(record.tt), record.tdb_apx, kTolExactLike) << record.iso;
    }
}

TEST_F(ConvertTimeDataDrivenTest, TdbToOtherScalesMatchReferenceData)
{
    for(const auto& record : epoch_records())
    {
        if(!has_ambiguous_posix(record.posix))
        {
            EXPECT_NEAR(tdb_tudat_to_utc_posix(record.tdb), record.posix, kTolTdb) << record.iso;
            EXPECT_NEAR(tdb_tudat_to_utc_tudat(record.tdb), record.utc, kTolTdb) << record.iso;
        }

        EXPECT_NEAR(tdb_tudat_to_tai_tudat(record.tdb), record.tai, kTolTdb) << record.iso;
        EXPECT_NEAR(tdb_tudat_to_tt_tudat(record.tdb), record.tt, kTolTdb) << record.iso;
        EXPECT_NEAR(tdb_tudat_to_tdb_apx_tudat(record.tdb), record.tdb_apx, kTolTdb) << record.iso;
    }
}

TEST_F(ConvertTimeDataDrivenTest, TdbApproxToOtherScalesMatchReferenceData)
{
    for(const auto& record : epoch_records())
    {
        EXPECT_NEAR(tdb_apx_tudat_to_utc_posix(record.tdb_apx), record.posix, kTolExactLike) << record.iso;
        EXPECT_NEAR(tdb_apx_tudat_to_utc_tudat(record.tdb_apx), record.utc, kTolExactLike) << record.iso;
        EXPECT_NEAR(tdb_apx_tudat_to_tai_tudat(record.tdb_apx), record.tai, kTolExactLike) << record.iso;
        EXPECT_NEAR(tdb_apx_tudat_to_tt_tudat(record.tdb_apx), record.tt, kTolExactLike) << record.iso;
        EXPECT_NEAR(tdb_apx_tudat_to_tdb_tudat(record.tdb_apx), record.tdb, kTolTdb) << record.iso;
    }
}

TEST_F(ConvertTimeDataDrivenTest, UtcIsoIdentityRoundTripForRecords)
{
    for(const auto& record : epoch_records())
    {
        EXPECT_EQ(utc_iso_tudat_to_utc_iso_tudat(record.iso), record.iso);
    }
}

TEST_F(ConvertTimeDataDrivenTest, NumericRoundTripUsingUtcIsStableForNonLeapSecondRows)
{
    for(const auto& record : epoch_records())
    {
        if(is_leap_second_iso(record.iso))
        {
            continue;
        }

        const double utc_from_posix = utc_posix_to_utc_tudat(record.posix);
        const double posix_from_utc = utc_tudat_to_utc_posix(utc_from_posix);
        EXPECT_NEAR(posix_from_utc, record.posix, kTolExactLike) << record.iso;

        const double tai_from_utc = utc_tudat_to_tai_tudat(record.utc);
        const double utc_from_tai = tai_tudat_to_utc_tudat(tai_from_utc);
        EXPECT_NEAR(utc_from_tai, record.utc, kTolExactLike) << record.iso;
    }
}
