cmake_minimum_required(VERSION 3.27)
project(tudatpy-utils)
include(FetchContent)
include(CTest)

find_package(tudat REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(nrlmsise00)

include_directories(${EIGEN3_INCLUDE_DIRS})

# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -ftime-report")
set(CMAKE_CXX_STANDARD 20)

add_compile_definitions(EIGEN_NO_DEBUG)
add_compile_definitions(
    NOTABLE_EPOCHS_FILE="${CMAKE_CURRENT_SOURCE_DIR}/time_conversion/test/notable_epochs.dat"
)
add_compile_options(
    -Wall
    -Wextra
    -Wunused
)

if(BUILD_TESTING)
    #
    # Code coverage (optional)
    #
    option(
        ENABLE_COVERAGE
        "Enable code coverage instrumentation"
        OFF
    )

    if(ENABLE_COVERAGE)
        if(CMAKE_CXX_COMPILER_ID
           MATCHES
           "GNU|Clang"
        )
            message(STATUS "Code coverage enabled")
            add_compile_options(
                -O0
                -g
                --coverage
            )
            add_link_options(--coverage)
        else()
            message(
                WARNING
                    "ENABLE_COVERAGE is ON but compiler is not GCC/Clang; coverage flags not applied"
            )
        endif()

        find_program(LCOV_EXECUTABLE lcov)
        find_program(GENHTML_EXECUTABLE genhtml)

        if(NOT LCOV_EXECUTABLE OR NOT GENHTML_EXECUTABLE)
            message(
                WARNING
                    "lcov/genhtml not found; 'coverage' target will be unavailable"
            )
        endif()

        find_program(GCOVR_EXECUTABLE gcovr)
        if(NOT GCOVR_EXECUTABLE)
            message(
                WARNING
                    "gcovr not found; 'coverage' target will be unavailable"
            )
        endif()
    endif()

    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
    )
    FetchContent_MakeAvailable(googletest)
endif()

add_subdirectory(time_conversion)
