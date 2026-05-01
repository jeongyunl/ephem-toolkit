#pragma once

#include "../time_converter.h"

class TimeConverterChronoUtc : public TimeConverter
{
public:
	static TimeConverterChronoUtc& instance()
	{
		static TimeConverterChronoUtc singleton;
		return singleton;
	}

	TimeConverterChronoUtc(const TimeConverterChronoUtc&) = delete;
	TimeConverterChronoUtc& operator=(const TimeConverterChronoUtc&) = delete;
	TimeConverterChronoUtc(TimeConverterChronoUtc&&) = delete;
	TimeConverterChronoUtc& operator=(TimeConverterChronoUtc&&) = delete;

private:
	TimeConverterChronoUtc() = default;
	~TimeConverterChronoUtc() = default;
};
