/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 bomwerk
 *
 * INGREDIENT 5 OF 5: the #ifdef variant.
 *
 * This is the file that makes the two build configurations produce different
 * binaries from an identical source tree. A static scanner reads the same bytes
 * either way and cannot tell which branch was taken - and that includes plain
 * `bomwerk scan`. Only observing the compiler distinguishes them.
 *
 *   config-a  NIGHTMARE_WITH_ZLIB      -> compiles third_party/zlib/*.c and reaches
 *                                         third_party/uthash by include path only
 *   config-b  NIGHTMARE_WITH_FREERTOS  -> compiles third_party/freertos/list.c,
 *                                         and never touches zlib or uthash
 */

#include "telemetry.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(NIGHTMARE_WITH_ZLIB)

#include "zlib.h"
#include "uthash.h"      /* header-only, present on the include path only in config-a */

/* A uthash record, so uthash.h is actually used and not just reachable. */
struct sample_record
{
    int sample_id;             /* the hash key */
    unsigned long compressed_size;
    UT_hash_handle hh;
};

static int roundtrip_through_zlib(void)
{
    /* Exercises both halves of zlib on purpose, because the two CVEs this corpus
     * is about live in different translation units: CVE-2018-25032 in deflate.c
     * (reached via compress2) and CVE-2022-37434 in inflate.c (via uncompress).
     * Calling only one of them would leave the other unlinked, and the SBOM would
     * be right to leave it out. */
    static const char kPayload[] =
        "nightmare telemetry frame: the vulnerable code is not merely present, "
        "it is linked into the binary and reachable from main().";

    unsigned char compressed[512];
    unsigned char restored[512];
    uLongf compressed_length = (uLongf) sizeof(compressed);
    uLongf restored_length = (uLongf) sizeof(restored);

    int zlib_status;

    zlib_status = compress2(compressed, &compressed_length,
                            (const Bytef *) kPayload, (uLong) sizeof(kPayload),
                            Z_BEST_COMPRESSION);
    if (zlib_status != Z_OK)
    {
        fprintf(stderr, "nightmare: compress2 -> %d (%s), z_stream is %u bytes\n",
                zlib_status, zError(zlib_status), (unsigned) sizeof(z_stream));
        return 1;
    }
    zlib_status = uncompress(restored, &restored_length, compressed, compressed_length);
    if (zlib_status != Z_OK)
    {
        fprintf(stderr, "nightmare: uncompress -> %d (%s)\n", zlib_status, zError(zlib_status));
        return 2;
    }
    if (restored_length != (uLongf) sizeof(kPayload) ||
        memcmp(restored, kPayload, sizeof(kPayload)) != 0)
    {
        return 3;
    }
    return 0;
}

int nightmare_telemetry_selftest(void)
{
    struct sample_record *table = NULL;
    struct sample_record *record;
    struct sample_record *found = NULL;
    const int kSampleId = 7;
    int result;

    result = roundtrip_through_zlib();
    if (result != 0)
    {
        return result;
    }

    record = (struct sample_record *) calloc(1, sizeof(*record));
    if (record == NULL)
    {
        return 4;
    }
    record->sample_id = kSampleId;
    record->compressed_size = 0UL;
    HASH_ADD_INT(table, sample_id, record);
    HASH_FIND_INT(table, &kSampleId, found);

    result = (found == record) ? 0 : 5;

    HASH_DEL(table, record);
    free(record);
    return result;
}

const char *nightmare_telemetry_backend(void)
{
    /* zlibVersion() is a zlib function call, so this string comes from the linked
     * library rather than from a macro a scanner could read out of a header. */
    static char backend[64];
    (void) snprintf(backend, sizeof(backend), "zlib %s + uthash", zlibVersion());
    return backend;
}

#elif defined(NIGHTMARE_WITH_FREERTOS)

#include "FreeRTOS.h"
#include "list.h"
#include "task.h"        /* for tskKERNEL_VERSION_NUMBER - the version that lies */

int nightmare_telemetry_selftest(void)
{
    /* The real work lives in rtos_shim.c, which is the translation unit that pulls
     * the forked list.c into the link. */
    extern int nightmare_rtos_selftest(void);
    return nightmare_rtos_selftest();
}

const char *nightmare_telemetry_backend(void)
{
    /* tskKERNEL_VERSION_NUMBER reads "V11.1.0" while third_party/freertos/list.c
     * is not V11.1.0; see third_party/freertos/PATCHES/0001. Every SBOM tool in
     * docs/RESULTS.md repeats this string and none of them notices. */
    return "FreeRTOS " tskKERNEL_VERSION_NUMBER " (forked)";
}

#else
#error "Define exactly one of NIGHTMARE_WITH_ZLIB or NIGHTMARE_WITH_FREERTOS. \
Use the CMake presets: cmake --preset config-a  (or config-b)."
#endif
