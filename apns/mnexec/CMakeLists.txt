cmake_minimum_required(VERSION 3.10)

project(mnexec)

set(CMAKE_C_FLAGS "-Wall -O2 -m64")
set(CMAKE_EXE_LINKER_FLAGS "-m64")
set(CMAKE_MODULE_LINKER_FLAGS "-m64")
set(CMAKE_SHARED_LINKER_FLAGS "-m64")

add_executable(mnexec
        mnexec.c
        )

install(TARGETS mnexec DESTINATION /usr/local/bin)