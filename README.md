### How to generate a coverage report for the project using CMake and the `coverage` target, follow these steps:

cmake -S . -B build -DBUILD_TESTING=ON -DENABLE_COVERAGE=ON
cmake --build build -j
cmake --build build --target coverage


Insert

Then open the file `build/coverage.html` in your web browser to view the coverage report.