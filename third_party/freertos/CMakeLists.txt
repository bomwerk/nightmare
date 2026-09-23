# Build file for the vendored FreeRTOS-Kernel subset. NOT an upstream file:
# upstream ships a full CMake package, and this is a deliberately minimal
# replacement that compiles ONE kernel translation unit. See third_party/SOURCES.md.
#
# Only list.c is compiled - not tasks.c, queue.c, timers.c or a heap. list.c is the
# smallest file that is still genuinely FreeRTOS, and nothing here is ever EXECUTED:
# this is a compile-and-link corpus, not a run-the-RTOS corpus.
#
# list.c CARRIES A LOCAL MODIFICATION (uxListInsertBounded). See
# PATCHES/0001-bounded-list-insert.patch.

add_library(nightmare_freertos STATIC
  list.c
)

# FreeRTOS V11.1.0 is C99. Without this, gcc 15's default of C23 rejects it.
set_target_properties(nightmare_freertos PROPERTIES C_STANDARD 99 C_STANDARD_REQUIRED ON)

target_include_directories(nightmare_freertos PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${CMAKE_CURRENT_SOURCE_DIR}/portable/ThirdParty/GCC/Posix
)

# The POSIX port is built on pthreads.
find_package(Threads REQUIRED)
target_link_libraries(nightmare_freertos PUBLIC Threads::Threads)
