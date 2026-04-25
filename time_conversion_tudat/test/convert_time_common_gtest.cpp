#include "test/convert_time_common_gtest.h"

#include <fstream>
#include <sstream>
#include <vector>

namespace convert_time_test
{

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
		if(fields.size() != 6)
		{
			throw std::runtime_error("Unexpected column count in notable epochs line: " + line);
		}

		records.push_back(EpochRecord{ fields[0],
									   std::stod(fields[1]),
									   std::stod(fields[2]),
									   std::stod(fields[3]),
									   std::stod(fields[4]),
									   std::stod(fields[5]) });
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

} // namespace convert_time_test
