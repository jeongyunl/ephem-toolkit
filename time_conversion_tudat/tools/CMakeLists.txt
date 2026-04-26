# Tools

add_executable(
    convert_time_tudat_cli convert_time_tudat_cli.cpp
                           convert_time_tudat_disp_tbl.cpp
)

# Allow includes like: #include "convert_time_disp_fn.h" (header lives in this
# directory)
target_include_directories(
    convert_time_tudat_cli PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
                                   ${CMAKE_CURRENT_SOURCE_DIR}/..
)

target_link_libraries(convert_time_tudat_cli PRIVATE convert_time_tudat)
