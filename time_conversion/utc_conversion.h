#pragma once

#include <chrono>

#if __cplusplus >= 202002L

// C++20 or later is supposed to have std::chrono::utc_time and std::chrono::parse, but some standard library
// versions may lack these features. We check for their presence and provide a fallback if needed.

#define HAS_CHRONO_UTC_CLOCK
#define HAS_CHRONO_PARSE

#ifdef _GLIBCXX_RELEASE

// std::chrono::utc_clock was added in GNU C++ library version 13 (not fully functional until version 14)
#if _GLIBCXX_RELEASE < 13
#undef HAS_CHRONO_UTC_CLOCK
#endif

// std::chrono::parse was added in GNU C++ library version 14
#if _GLIBCXX_RELEASE < 14
#undef HAS_CHRONO_PARSE
#endif

#elif defined(_LIBCPP_STD_VER)

#if _LIBCPP_STD_VER < 20 || !_LIBCPP_HAS_TIME_ZONE_DATABASE
#undef HAS_CHRONO_UTC_CLOCK
#undef HAS_CHRONO_PARSE
#endif

#endif

#endif
