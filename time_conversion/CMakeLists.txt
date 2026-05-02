add_library(
    convert_time STATIC
    convert_time_leap_transition.cpp
    time_converter.cpp
    base/time_converter_base.cpp
    base/iso8601.cpp
    base/base_dispatch_table.cpp
    chrono/time_converter_chrono.cpp
    chrono/chrono_dispatch_table.cpp
    tudat/time_converter_tudat.cpp
    tudat/tudat_dispatch_table.cpp
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
                           test/convert_time_gtest_common.cpp
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
        convert_time_disp_tbl_gtest test/convert_time_disp_tbl_gtest.cpp
                                    test/convert_time_gtest_common.cpp
    )

    add_executable(
        convert_time_iso8601_gtest test/convert_time_iso8601_gtest.cpp
    )

    add_executable(
        convert_time_epochs_gtest test/convert_time_epochs_gtest.cpp
    )

    add_executable(
        convert_time_j2000_gtest test/convert_time_j2000_gtest.cpp
                                 test/convert_time_gtest_common.cpp
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

    target_link_libraries(
        convert_time_epochs_gtest
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

    target_include_directories(
        convert_time_epochs_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    target_link_libraries(
        convert_time_disp_tbl_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    if(ENABLE_COVERAGE)
        target_link_libraries(
            convert_time_disp_tbl_gtest PRIVATE coverage_config
        )
    endif()

    target_include_directories(
        convert_time_disp_tbl_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/tools
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    add_executable(
        convert_time_chrono_gtest test/time_converter_chrono_gtest.cpp
                                  test/convert_time_gtest_common.cpp
    )

    target_link_libraries(
        convert_time_chrono_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    if(ENABLE_COVERAGE)
        target_link_libraries(
            convert_time_chrono_gtest PRIVATE coverage_config
        )
    endif()

    target_include_directories(
        convert_time_chrono_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    add_executable(
        convert_time_tudat_gtest test/convert_time_tudat_gtest.cpp
                                 test/convert_time_gtest_common.cpp
    )

    target_link_libraries(
        convert_time_tudat_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_tudat_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    add_executable(
        convert_time_tudat_disp_tbl_gtest
        test/convert_time_tudat_disp_tbl_gtest.cpp
        test/convert_time_gtest_common.cpp
    )

    target_link_libraries(
        convert_time_tudat_disp_tbl_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_tudat_disp_tbl_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/tools
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    include(GoogleTest)
    gtest_discover_tests(convert_time_gtest)
    gtest_discover_tests(convert_time_disp_tbl_gtest)
    gtest_discover_tests(convert_time_iso8601_gtest)
    gtest_discover_tests(convert_time_epochs_gtest)
    gtest_discover_tests(convert_time_j2000_gtest)
    gtest_discover_tests(convert_time_chrono_gtest)
    gtest_discover_tests(convert_time_tudat_gtest)
    gtest_discover_tests(convert_time_tudat_disp_tbl_gtest)
endif()
