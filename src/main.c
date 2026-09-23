/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 bomwerk
 *
 * The whole "product". It exists to give the linker a reason to pull the vendored
 * libraries in, so that "this component ships" is a fact about a binary rather
 * than a guess about a directory listing.
 *
 * Build it two ways and compare the SBOMs:
 *     cmake --preset config-a && cmake --build build/config-a
 *     cmake --preset config-b && cmake --build build/config-b
 */

#include "telemetry.h"

#include <stdio.h>

#if defined(NIGHTMARE_WITH_ZLIB)
/* config-a links two prebuilt archives (third_party/*-prebuilt). Calling into both is
 * what makes the linker pull them in, and makes the binary print their real versions,
 * which is the ground truth a scanner can be checked against. */
#include "cJSON.h"
#include "sqlite3.h"
#endif

#if defined(NIGHTMARE_ENABLE_OPENSSL)
extern const char *nightmare_crypto_backend(void);
extern int nightmare_crypto_selftest(void);
#endif

int main(void)
{
    int result = nightmare_telemetry_selftest();

    printf("nightmare: telemetry backend = %s\n", nightmare_telemetry_backend());
    if (result != 0)
    {
        printf("nightmare: telemetry selftest FAILED (%d)\n", result);
        return result;
    }

#if defined(NIGHTMARE_ENABLE_OPENSSL)
    printf("nightmare: crypto backend    = %s\n", nightmare_crypto_backend());
    result = nightmare_crypto_selftest();
    if (result != 0)
    {
        printf("nightmare: crypto selftest FAILED (%d)\n", result);
        return result;
    }
#endif

#if defined(NIGHTMARE_WITH_ZLIB)
    printf("nightmare: prebuilt       = sqlite %s, cjson %s\n", sqlite3_libversion(),
           cJSON_Version());
#endif

    printf("nightmare: ok\n");
    return 0;
}
