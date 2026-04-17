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
    NOTABLE_EPOCHS_FILE="${CMAKE_CURRENT_SOURCE_DIR}/test/notable_epochs.dat"
)
add_compile_options(
    -Wall
    -Wextra
    -Wunused
)

# dispatch table-based implementation add_executable( convert_time_disp_tbl_cli
# convert_time_disp_tbl_cli.cpp convert_time.cpp ) target_link_libraries(
# convert_time_disp_tbl_cli PUBLIC ${Tudat_PROPAGATION_LIBRARIES} )

# convert_time() based implementation
add_executable(
    convert_time_disp_fn_cli
    convert_time_disp_fn_cli.cpp
    convert_time_disp_tbl.cpp
    convert_time.cpp
)
target_link_libraries(
    convert_time_disp_fn_cli PUBLIC ${Tudat_PROPAGATION_LIBRARIES}
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

    #
    # convert_time_gtest
    #

    add_executable(
        convert_time_gtest
        test/convert_time_gtest.cpp
        test/convert_time_common_gtest.cpp
        convert_time.cpp
    )

    target_link_libraries(
        convert_time_gtest
        PRIVATE ${Tudat_PROPAGATION_LIBRARIES}
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
    )

    #
    # convert_time_tmpl_gtest
    #

    add_executable(
        convert_time_tmpl_gtest
        test/convert_time_tmpl_gtest.cpp
        test/convert_time_common_gtest.cpp
        convert_time.cpp
    )

    target_link_libraries(
        convert_time_tmpl_gtest
        PRIVATE ${Tudat_PROPAGATION_LIBRARIES}
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_tmpl_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
    )

    #
    # convert_time_disp_fn_gtest
    #

    add_executable(
        convert_time_disp_fn_gtest
        test/convert_time_disp_fn_gtest.cpp
        test/convert_time_common_gtest.cpp
        convert_time.cpp
    )

    target_link_libraries(
        convert_time_disp_fn_gtest
        PRIVATE ${Tudat_PROPAGATION_LIBRARIES}
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_disp_fn_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
    )

    #

    include(GoogleTest)
    gtest_discover_tests(convert_time_gtest)
    gtest_discover_tests(convert_time_tmpl_gtest)
    gtest_discover_tests(convert_time_disp_fn_gtest)

    #
    # Coverage report target
    #
    if(ENABLE_COVERAGE)
        if(GCOVR_EXECUTABLE)
            add_custom_target(
                coverage
                COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
                COMMAND
                    ${GCOVR_EXECUTABLE} -r ${CMAKE_CURRENT_SOURCE_DIR}
                    --exclude "${CMAKE_BINARY_DIR}/_deps/.*" --exclude
                    ".*/_deps/.*" --exclude ".*googletest.*" --exclude
                    "/usr/.*" --html --html-details -o coverage.html
                WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                COMMENT
                    "Running tests and generating coverage report: ${CMAKE_BINARY_DIR}/coverage.html"
                VERBATIM
            )
        elseif(LCOV_EXECUTABLE AND GENHTML_EXECUTABLE)
            add_custom_target(
                coverage
                COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
                COMMAND ${LCOV_EXECUTABLE} --directory . --capture
                        --output-file coverage.info
                COMMAND
                    ${LCOV_EXECUTABLE} --remove coverage.info '/usr/*'
                    '${googletest_SOURCE_DIR}/*' '${CMAKE_BINARY_DIR}/_deps/*'
                    --output-file coverage.info
                COMMAND ${GENHTML_EXECUTABLE} coverage.info --output-directory
                        coverage
                WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                COMMENT
                    "Running tests and generating coverage report in ${CMAKE_BINARY_DIR}/coverage"
                VERBATIM
            )
        endif()
    endif()
endif()
