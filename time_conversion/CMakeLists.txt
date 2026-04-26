add_library(
    convert_time STATIC
    convert_time_iso8601.cpp
    convert_time_j2000.cpp
    convert_time_leap_transition.cpp
)

# Apply coverage flags only to this project targets when enabled
if(BUILD_TESTING AND ENABLE_COVERAGE)
    target_link_libraries(convert_time PUBLIC coverage_config)
endif()

target_include_directories(convert_time PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

target_link_libraries(convert_time PUBLIC ${Tudat_PROPAGATION_LIBRARIES})

add_subdirectory(tools)

if(BUILD_TESTING)
    add_executable(
        convert_time_gtest test/convert_time_gtest.cpp
                           test/convert_time_common_gtest.cpp
    )

    target_link_libraries(
        convert_time_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    if(ENABLE_COVERAGE)
        target_link_libraries(convert_time_gtest PRIVATE coverage_config)
    endif()

    target_include_directories(
        convert_time_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    add_executable(
        convert_time_disp_fn_gtest test/convert_time_disp_fn_gtest.cpp
                                   test/convert_time_common_gtest.cpp
    )

    add_executable(
        convert_time_iso8601_gtest test/convert_time_iso8601_gtest.cpp
    )

    add_executable(
        convert_time_j2000_gtest test/convert_time_j2000_gtest.cpp
                                 test/convert_time_common_gtest.cpp
    )

    target_link_libraries(
        convert_time_j2000_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    if(ENABLE_COVERAGE)
        target_link_libraries(convert_time_j2000_gtest PRIVATE coverage_config)
    endif()

    target_include_directories(
        convert_time_j2000_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    target_link_libraries(
        convert_time_iso8601_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    if(ENABLE_COVERAGE)
        target_link_libraries(
            convert_time_iso8601_gtest PRIVATE coverage_config
        )
    endif()

    target_include_directories(
        convert_time_iso8601_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    target_link_libraries(
        convert_time_disp_fn_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    if(ENABLE_COVERAGE)
        target_link_libraries(
            convert_time_disp_fn_gtest PRIVATE coverage_config
        )
    endif()

    target_include_directories(
        convert_time_disp_fn_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/tools
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    include(GoogleTest)
    gtest_discover_tests(convert_time_gtest)
    gtest_discover_tests(convert_time_disp_fn_gtest)
    gtest_discover_tests(convert_time_iso8601_gtest)
    gtest_discover_tests(convert_time_j2000_gtest)
endif()
