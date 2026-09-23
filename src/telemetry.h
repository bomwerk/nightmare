/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 bomwerk
 *
 * First-party code. Nothing in src/ is third-party.
 */
#ifndef NIGHTMARE_TELEMETRY_H
#define NIGHTMARE_TELEMETRY_H

#include <stddef.h>

/* Returns 0 on success. Which implementation you get depends on the build
 * configuration, not on anything in this header - see telemetry.c. */
int nightmare_telemetry_selftest(void);

/* Names the backend the CURRENT BINARY was built with. This is the string a
 * human can read off the built artifact to see which configuration they have,
 * and it is why the two configurations are distinguishable at runtime as well
 * as in the SBOM. */
const char *nightmare_telemetry_backend(void);

#endif /* NIGHTMARE_TELEMETRY_H */
