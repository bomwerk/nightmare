/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 bomwerk
 *
 * Compiled only with -DNIGHTMARE_ENABLE_OPENSSL=ON, which is off by default and
 * requires the submodule to be checked out:
 *
 *     git submodule update --init --depth 1 third_party/openssl
 *
 * Detection doesn't need this: bomwerk reads .gitmodules as a file, so a shallow
 * clone with no submodule init already reports the dependency (and warns that its
 * answer is incomplete). This file exists so that the "statically linked OpenSSL"
 * claim can be demonstrated by someone who wants to pay the build cost, not so
 * that everyone has to.
 */

#include <openssl/opensslv.h>
#include <openssl/sha.h>

#include <string.h>

const char *nightmare_crypto_backend(void)
{
    return OPENSSL_VERSION_TEXT;
}

int nightmare_crypto_selftest(void)
{
    static const char kMessage[] = "nightmare";
    unsigned char digest[SHA256_DIGEST_LENGTH];

    if (SHA256((const unsigned char *) kMessage, strlen(kMessage), digest) == NULL)
    {
        return 1;
    }
    return 0;
}
