### How to generate a coverage report for the project using CMake and the `coverage` target, follow these steps:

cmake -S . -B coverage -DBUILD_TESTING=ON -DENABLE_COVERAGE=ON
cmake --build coverage -j
cmake --build coverage --target coverage


Insert

Then open the file `coverage/coverage.html` in your web browser to view the coverage report.

