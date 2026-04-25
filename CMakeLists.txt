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

            # Coverage flags must be applied to *targets* (not globally),
            # otherwise external dependencies (e.g. Tudat) may be rebuilt with
            # coverage.
            add_library(coverage_config INTERFACE)
            target_compile_options(
                coverage_config
                INTERFACE -O0
                          -g
                          --coverage
            )
            target_link_options(
                coverage_config
                INTERFACE
                --coverage
            )

            # Tools
            find_program(LCOV_EXECUTABLE lcov)
            find_program(GENHTML_EXECUTABLE genhtml)
            find_program(GCOVR_EXECUTABLE gcovr)

            if(NOT GCOVR_EXECUTABLE)
                message(
                    WARNING
                        "gcovr not found; 'coverage' target will be unavailable"
                )
            endif()

            # A convenient target that: 1) runs all tests 2) generates an HTML
            # report in <build>/coverage/
            if(GCOVR_EXECUTABLE)
                add_custom_target(
                    coverage
                    COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
                    COMMAND
                        ${GCOVR_EXECUTABLE} -r ${CMAKE_CURRENT_SOURCE_DIR}
                        --object-directory ${CMAKE_BINARY_DIR} --exclude
                        '.*_deps/.*' --exclude '.*CMakeFiles/.*' --exclude
                        '.*googletest.*' --exclude '.*test/.*' --html
                        --html-details -o
                        ${CMAKE_BINARY_DIR}/coverage/index.html
                    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                    USES_TERMINAL
                    COMMENT "Running tests and generating coverage report"
                )
            endif()
        else()
            message(
                WARNING
                    "ENABLE_COVERAGE is ON but compiler is not GCC/Clang; coverage flags not applied"
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
add_subdirectory(time_conversion_tudat)
