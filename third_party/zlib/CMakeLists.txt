# Build file for the vendored zlib subset. NOT an upstream zlib file: upstream ships a
# full configure/CMake setup, and this is a deliberately minimal replacement that
# compiles the deflate/inflate core and nothing else. See third_party/SOURCES.md.
#
# The gz* translation units are excluded on purpose: they add nothing this corpus
# demonstrates. gzguts.h itself is vendored because zutil.c includes it.

add_library(nightmare_zlib STATIC
  adler32.c
  compress.c
  crc32.c
  deflate.c      # CVE-2018-25032 lives here
  inflate.c      # CVE-2022-37434 (9.8 Critical) lives here
  inffast.c
  inftrees.c
  trees.c
  uncompr.c
  zutil.c
)

# zlib 1.2.11 is 2017-era C. Without this, a modern compiler defaulting to C23
# (gcc 15 does) rejects it outright rather than warning. See the root CMakeLists.
set_target_properties(nightmare_zlib PROPERTIES C_STANDARD 99 C_STANDARD_REQUIRED ON)

# Upstream's configure script probes for this; we are Linux/POSIX-only here.
#
# Do NOT define Z_SOLO. It does stop zutil.c from including gzguts.h, but it also
# removes zlib's default allocator: deflateInit/inflateInit then reject a NULL
# zalloc with Z_STREAM_ERROR, which is exactly what compress2()/uncompress() pass.
# The build compiles and every compression call fails at runtime. gzguts.h is
# vendored instead (a header only - the gz*.c translation units stay excluded).
target_compile_definitions(nightmare_zlib PRIVATE Z_HAVE_UNISTD_H)

target_include_directories(nightmare_zlib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
