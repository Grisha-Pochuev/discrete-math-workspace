cmake_minimum_required(VERSION 3.18)

project(run052_adaptive_worker VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_BUILD_WITH_INSTALL_RPATH TRUE)

find_package(ortools REQUIRED CONFIG)

add_executable(run052_adaptive_worker main.cpp)
target_link_libraries(run052_adaptive_worker PRIVATE ortools::ortools)
