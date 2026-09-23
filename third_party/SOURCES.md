# third_party: where every file came from

Every file here matches its upstream byte for byte at a pinned commit or release
archive. The exceptions are marked in the tables: files we added (`added by us`), files
we compiled (`built by us`), and one file we changed on purpose (`modified: yes`).

`third_party/pins.json` is the machine-readable record. The per-file tables below are
generated from it by `python3 tools/render_sources.py`; the text around them is written
by hand. `bash tools/verify_vendored.sh` downloads each upstream at its pin and compares
every file, and CI runs it on every push. If that script fails, this document is wrong.

A file can't sit in a vendor directory without a row in `pins.json`. The verifier fails
on any file it doesn't know about.

| component | upstream | pinned ref | pin | license | in this repo |
|---|---|---|---|---|---|
| zlib | madler/zlib | `v1.2.11` | commit `cacf7f1d4e3d` | Zlib | source |
| freertos | FreeRTOS/FreeRTOS-Kernel | `V11.1.0` | commit `dbf70559b27d` | MIT | source, one file modified |
| uthash | troydhanson/uthash | `v2.4.0` | commit `a49bed0b4abb` | revised BSD | source |
| stb | nothings/stb | `master@2026-09-18` | commit `2c980bb59875` | MIT or Unlicense | source |
| sqlite | sqlite.org release zip | `3.41.2` | zip sha256 `01df06a84803` | public domain | header + prebuilt `.a` |
| cjson | DaveGamble/cJSON | `v1.7.15` | commit `d348621ca935` | MIT | header + prebuilt `.a` |
| openssl | openssl/openssl | `openssl-3.0.7` | commit `19cc035b6c6f` | Apache-2.0 | no, git submodule |
| tinyxml2 | leethomason/tinyxml2 | `9.0.0` | commit `1dee28e51f91` | Zlib | no, CMake `FetchContent` |

## zlib

<!-- BEGIN files:zlib -->
| file | upstream path | modified | note |
|---|---|---|---|
| `CMakeLists.txt` | not applicable | **added by us** | written by us: a small replacement for upstream's build setup that compiles the deflate/inflate core and leaves out gz*.c. It does not define Z_SOLO (see the file) |
| `LICENSE` | not applicable | **added by us** | written by us: upstream has no LICENSE file, so this copies the text from lines 4-23 of zlib.h. A vendor directory without a license file looks careless, and license detection reads this file |
| `README` | `README` | no | upstream README, unchanged; the license text is at the end |
| `adler32.c` | `adler32.c` | no |  |
| `compress.c` | `compress.c` | no |  |
| `crc32.c` | `crc32.c` | no |  |
| `crc32.h` | `crc32.h` | no |  |
| `deflate.c` | `deflate.c` | no | CVE-2018-25032 is here; compiled in config-a |
| `deflate.h` | `deflate.h` | no |  |
| `gzguts.h` | `gzguts.h` | no | header only. zutil.c includes it unless Z_SOLO is defined, and Z_SOLO would turn off zlib's default allocator. The gz*.c files are still left out |
| `inffast.c` | `inffast.c` | no |  |
| `inffast.h` | `inffast.h` | no |  |
| `inffixed.h` | `inffixed.h` | no |  |
| `inflate.c` | `inflate.c` | no | CVE-2022-37434 (CVSS 9.8) is here; compiled in config-a |
| `inflate.h` | `inflate.h` | no |  |
| `inftrees.c` | `inftrees.c` | no |  |
| `inftrees.h` | `inftrees.h` | no |  |
| `trees.c` | `trees.c` | no |  |
| `trees.h` | `trees.h` | no |  |
| `uncompr.c` | `uncompr.c` | no |  |
| `zconf.h` | `zconf.h` | no |  |
| `zlib.h` | `zlib.h` | no | declares ZLIB_VERSION "1.2.11", which is what version detection reads |
| `zutil.c` | `zutil.c` | no |  |
| `zutil.h` | `zutil.h` | no |  |

_22 of 24 file(s) match upstream byte for byte at `cacf7f1d4e3d`. `tools/verify_vendored.sh` checks this._
<!-- END files:zlib -->

Two notes on this table:

- Upstream zlib has no `LICENSE` file. The license text is at the bottom of `README`
  and in the comment at the top of `zlib.h`. We added `third_party/zlib/LICENSE`, which
  starts with `zlib License` followed by that text copied from `zlib.h`. It's marked
  `added by us` and the verifier skips it. A public vendor directory without a license
  file looks careless, and the file is also what license detection reads.
- The zlib license asks that altered versions be clearly marked. We changed nothing, so
  there is nothing to mark, and the verifier shows it.

The `gz*.c` files are not vendored because nothing here uses them. `gzguts.h` is,
because `zutil.c` includes it.

## freertos

<!-- BEGIN files:freertos -->
| file | upstream path | modified | note |
|---|---|---|---|
| `CMakeLists.txt` | not applicable | **added by us** | written by us: compiles list.c only, with the POSIX port on the include path |
| `LICENSE.md` | `LICENSE.md` | no | MIT, unchanged |
| `PATCHES/0001-bounded-list-insert.patch` | not applicable | **added by us** | written by us: the local change to list.c as a reversible diff |
| `README.md` | `README.md` | no | upstream README, unchanged |
| `include/FreeRTOS.h` | `include/FreeRTOS.h` | no |  |
| `include/FreeRTOSConfig.h` | `examples/template_configuration/FreeRTOSConfig.h` | no | unchanged from upstream's examples/template_configuration, which is why the upstream path differs. Vendor kernel drops such as STM32Cube and ESP-IDF also ship a config inside the kernel tree |
| `include/deprecated_definitions.h` | `include/deprecated_definitions.h` | no | 57 includes, all behind #ifdefs for old ports; none apply to the POSIX port |
| `include/list.h` | `include/list.h` | no | header for list.c |
| `include/mpu_wrappers.h` | `include/mpu_wrappers.h` | no |  |
| `include/portable.h` | `include/portable.h` | no |  |
| `include/projdefs.h` | `include/projdefs.h` | no |  |
| `include/task.h` | `include/task.h` | no | declares tskKERNEL_VERSION_NUMBER "V11.1.0" at line 56. Version detection reads it, and it is also why the fork goes unnoticed |
| `list.c` | `list.c` | **yes** | the fork. Lines 1-246 are unchanged upstream code; uxListInsertBounded() was added below a banner comment and is not in any FreeRTOS release. Reversing the patch with `git apply -R` restores the upstream file exactly, and the verifier checks this. tskKERNEL_VERSION_NUMBER was left at V11.1.0 on purpose |
| `portable/ThirdParty/GCC/Posix/portmacro.h` | `portable/ThirdParty/GCC/Posix/portmacro.h` | no | the POSIX port header, so the kernel compiles on an ordinary Linux machine |

_11 of 14 file(s) match upstream byte for byte at `dbf70559b27d`. `tools/verify_vendored.sh` checks this._
<!-- END files:freertos -->

`list.c` is changed on purpose and is the only changed file in the repo.
`PATCHES/0001-bounded-list-insert.patch` is a real diff against the pinned commit, so
`git apply -R` gets the upstream file back exactly, and the verifier checks that it does.

`tskKERNEL_VERSION_NUMBER` was left at `"V11.1.0"` on purpose, even though the code no
longer is V11.1.0. That mismatch is what makes vendor forks hard to track, and fixing it
would remove the ingredient. MIT doesn't require marking changes; the banner comment in
`list.c`, the patch file and this note are there so nobody is misled.

`FreeRTOSConfig.h` comes from upstream's own `examples/template_configuration/`, which
is why its upstream path differs from where it sits here. Vendor kernel drops such as
STM32Cube and ESP-IDF ship a config inside the kernel tree too.

## uthash

<!-- BEGIN files:uthash -->
| file | upstream path | modified | note |
|---|---|---|---|
| `LICENSE` | `LICENSE` | no | revised BSD. Contains none of the seven license names bomwerk looks for (checked), so bomwerk reports no license; GROUND-TRUTH.md says so |
| `uthash.h` | `src/uthash.h` | no | the whole library, header-only. config-a reaches it only through an include path |

_2 of 2 file(s) match upstream byte for byte at `a49bed0b4abb`. `tools/verify_vendored.sh` checks this._
<!-- END files:uthash -->

## stb

<!-- BEGIN files:stb -->
| file | upstream path | modified | note |
|---|---|---|---|
| `LICENSE` | `LICENSE` | no | dual: 'ALTERNATIVE A - MIT License' or 'ALTERNATIVE B - Public Domain (Unlicense)'. bomwerk's license check stops at 'MIT License' and reports MIT, dropping the Unlicense option; GROUND-TRUTH.md records this |
| `stb_image.h` | `stb_image.h` | no | not used by any target, include path or #include in either configuration. `#define STBI_VERSION 1` is a number, not a quoted string, so no version is found and the name comes from the folder |

_2 of 2 file(s) match upstream byte for byte at `2c980bb59875`. `tools/verify_vendored.sh` checks this._
<!-- END files:stb -->

## sqlite

<!-- BEGIN files:sqlite -->
| file | upstream path | modified | note |
|---|---|---|---|
| `include/sqlite3.h` | `sqlite-amalgamation-3410200/sqlite3.h` | no | declares SQLITE_VERSION "3.41.2", the only place in this directory where the version is written as text |
| `lib/libsqlite3.a` | built from `sqlite-amalgamation-3410200/sqlite3.c` | **built by us**, sha256 `7883a783efea` | compiled by tools/build_prebuilt.sh from the pinned zip; linked in config-a only |

_1 of 2 file(s) match upstream byte for byte at the release archive with sha256 `01df06a84803`. `tools/verify_vendored.sh` checks this._
<!-- END files:sqlite -->

SQLite publishes its single-file "amalgamation" only as a release zip, not in git, so the
pin is the zip's sha256 rather than a commit. `sqlite3.h` is taken from that zip
unchanged. `libsqlite3.a` is compiled from the zip's `sqlite3.c` by
`tools/build_prebuilt.sh`, with the exact flags listed in that script. That is how an SDK
vendor hands you a library: a header and a binary. SQLite is in the public domain; its
source carries a blessing instead of a license, so there is no license file to vendor.

## cjson

<!-- BEGIN files:cjson -->
| file | upstream path | modified | note |
|---|---|---|---|
| `LICENSE` | `LICENSE` | no | MIT text, but without the words 'MIT License', so license detection by substring doesn't recognize it |
| `include/cJSON.h` | `cJSON.h` | no | the version appears only as three numbers (1, 7, 15), never as "1.7.15" |
| `lib/libcjson.a` | built from `cJSON.c` | **built by us**, sha256 `6e026e04af93` | compiled by tools/build_prebuilt.sh from the pinned commit; linked in config-a only |

_2 of 3 file(s) match upstream byte for byte at `d348621ca935`. `tools/verify_vendored.sh` checks this._
<!-- END files:cjson -->

cJSON's `v1.7.15` tag is an annotated tag. Its tag object is `8e774f9d59d0` and the
commit it points to is `d348621ca935`. The pin is the commit. `libcjson.a` is compiled
from `cJSON.c` at that commit by `tools/build_prebuilt.sh`.

This one was chosen because `cJSON.h` only writes its version as three separate numbers
(`CJSON_VERSION_MAJOR 1`, `_MINOR 7`, `_PATCH 15`), never as the string "1.7.15". See
`GROUND-TRUTH.md` for what that does to every tool, bomwerk included.

About the prebuilt archives in general: the same compiler and flags reproduce them byte
for byte (`ar` runs in deterministic mode, with uid 0 and mtime 0). A different compiler
produces different bytes, which is expected. What's pinned is the source, and
`pins.json` records the toolchain the committed archives came from.

## openssl

No OpenSSL file is in this repo. It is a git submodule pinned at `openssl-3.0.7`
(November 2022) and never updated. That is one of the patterns the corpus reproduces.

Detecting it needs no checkout. bomwerk reads `.gitmodules` and the git metadata as files
instead of running `git submodule status`, so a `--depth 1` clone without the submodule
is enough to see the dependency. Building against OpenSSL is a separate option
(`-DNIGHTMARE_ENABLE_OPENSSL=ON`) and needs the checkout.

## tinyxml2

No tinyxml2 file is in this repo either. The root `CMakeLists.txt` declares it with
`FetchContent_Declare`, pinned to commit `1dee28e51f91` (tag `9.0.0`), which is how many
CMake projects pull dependencies. CMake downloads it only with
`-DNIGHTMARE_ENABLE_XML=ON`, so the default build needs no network. The declaration is
there either way, so every static scanner reads the same file.
