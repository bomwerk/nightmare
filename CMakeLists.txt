# nightmare - a public SBOM test corpus.
#
# Build it two ways and compare the SBOMs:
#     cmake --preset config-a && cmake --build build/config-a
#     cmake --preset config-b && cmake --build build/config-b
#
# Identical source tree, different components in the binary. See GROUND-TRUTH.md.

cmake_minimum_required(VERSION 3.22)
project(nightmare LANGUAGES C VERSION 0.1.0)

# Required. The vendored code here is 2017-era zlib and C99 FreeRTOS, while a
# modern compiler defaults to C23 (gcc 15 does) where an implicit function
# declaration is an error rather than a warning. Without this the corpus fails to
# build for a reason that has nothing to do with the corpus.
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

# Do not enable -Werror or -Wundef. This corpus builds pinned third-party code, and
# newer compilers can add diagnostics that do not affect the scenario being tested.
# In particular, -Wundef would fire on FreeRTOS's own
# `#if ( configUSE_LIST_DATA_INTEGRITY_CHECK_BYTES == 0 )`, which relies on the
# identifier being undefined.

option(NIGHTMARE_ENABLE_COMPRESSION
       "Compile the vendored zlib and the uthash-backed telemetry path" ON)
option(NIGHTMARE_ENABLE_RTOS_SHIM
       "Compile the forked FreeRTOS kernel list module" OFF)
option(NIGHTMARE_ENABLE_XML
       "Download and build tinyxml2 through FetchContent (needs network at configure time)" OFF)
option(NIGHTMARE_ENABLE_OPENSSL
       "Build against the pinned OpenSSL submodule (requires a submodule checkout)" OFF)

if(NIGHTMARE_ENABLE_COMPRESSION AND NIGHTMARE_ENABLE_RTOS_SHIM)
  message(FATAL_ERROR
    "NIGHTMARE_ENABLE_COMPRESSION and NIGHTMARE_ENABLE_RTOS_SHIM are mutually "
    "exclusive: the two configurations exist to link different "
    "components. Use `cmake --preset config-a` or `cmake --preset config-b`.")
endif()
if(NOT NIGHTMARE_ENABLE_COMPRESSION AND NOT NIGHTMARE_ENABLE_RTOS_SHIM)
  message(FATAL_ERROR
    "Enable exactly one of NIGHTMARE_ENABLE_COMPRESSION or NIGHTMARE_ENABLE_RTOS_SHIM.")
endif()

# tinyxml2 is declared the way many CMake projects pull a dependency: FetchContent,
# pinned by commit. The declaration is always here, so every static scanner reads the
# same file; the download only happens with -DNIGHTMARE_ENABLE_XML=ON, so the default
# build needs no network.
include(FetchContent)
FetchContent_Declare(
  tinyxml2
  GIT_REPOSITORY https://github.com/leethomason/tinyxml2.git
  GIT_TAG        1dee28e51f9175a31955b9791c74c430fe13dc82 # 9.0.0
)

add_executable(nightmare
  src/main.c
  src/telemetry.c
)

if(NIGHTMARE_ENABLE_COMPRESSION)
  add_subdirectory(third_party/zlib)
  target_compile_definitions(nightmare PRIVATE NIGHTMARE_WITH_ZLIB)
  target_link_libraries(nightmare PRIVATE nightmare_zlib)

  # Two libraries that arrive PREBUILT: a header and a .a, no source. config-a links
  # both, so the linker really consumes them; config-b does not. See
  # tools/build_prebuilt.sh for where the archives come from.
  target_include_directories(nightmare PRIVATE
    third_party/sqlite-prebuilt/include
    third_party/cjson-prebuilt/include)
  target_link_libraries(nightmare PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/sqlite-prebuilt/lib/libsqlite3.a
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/cjson-prebuilt/lib/libcjson.a
    m)  # cJSON uses libm

  # uthash is header-only and is reached by include path alone; there is no library
  # to link. This is the weakest kind of usage: a component that is really used, with
  # no compiled object and no linked archive to prove it. No rival tool in
  # docs/RESULTS.md models this distinction.
  target_include_directories(nightmare PRIVATE third_party/uthash)
endif()

if(NIGHTMARE_ENABLE_RTOS_SHIM)
  add_subdirectory(third_party/freertos)
  target_compile_definitions(nightmare PRIVATE NIGHTMARE_WITH_FREERTOS)
  target_sources(nightmare PRIVATE src/rtos_shim.c)
  target_link_libraries(nightmare PRIVATE nightmare_freertos)
endif()

if(NIGHTMARE_ENABLE_OPENSSL)
  set(kOpenSslHeader "${CMAKE_CURRENT_SOURCE_DIR}/third_party/openssl/include/openssl/opensslv.h")
  if(NOT EXISTS "${kOpenSslHeader}")
    message(FATAL_ERROR
      "NIGHTMARE_ENABLE_OPENSSL=ON but the OpenSSL submodule is not checked out.\n"
      "Run:\n"
      "    git submodule update --init --depth 1 third_party/openssl\n"
      "Detection does not need this: a shallow clone with no submodule init already "
      "reports the dependency. Only BUILDING against OpenSSL does.")
  endif()
  find_package(OpenSSL REQUIRED)
  target_compile_definitions(nightmare PRIVATE NIGHTMARE_ENABLE_OPENSSL)
  target_sources(nightmare PRIVATE src/crypto_shim.c)
  target_link_libraries(nightmare PRIVATE OpenSSL::Crypto)
endif()

if(NIGHTMARE_ENABLE_XML)
  enable_language(CXX)  # tinyxml2 is C++; the rest of the corpus is C
  FetchContent_MakeAvailable(tinyxml2)
  target_compile_definitions(nightmare PRIVATE NIGHTMARE_ENABLE_XML)
  target_link_libraries(nightmare PRIVATE tinyxml2)
endif()

# Nothing references third_party/stb, on purpose: no target, no include
# directory, no #include, in either configuration. Do not "fix" this.

message(STATUS "nightmare: compression=${NIGHTMARE_ENABLE_COMPRESSION} "
               "rtos=${NIGHTMARE_ENABLE_RTOS_SHIM} openssl=${NIGHTMARE_ENABLE_OPENSSL}")
