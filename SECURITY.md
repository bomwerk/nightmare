# Security policy

This repository contains known-vulnerable code on purpose. zlib 1.2.11 is vendored with
its CVEs, as source, to test whether SBOM tools find it. None of this code is deployed
as a service, and nothing here should be shipped in a product.

**A problem in this repository's own code** (the CMake build, `tools/`, the CI
workflows): please email info@bomwerk.com instead of opening a public issue. We'll
reply within five business days.

**A problem in a third-party component** (zlib, FreeRTOS, uthash, stb, SQLite, cJSON,
OpenSSL, tinyxml2): please report it to that project. This repository deliberately
does not patch or track vulnerabilities in the code it vendors, because finding them is
what the corpus is for.
