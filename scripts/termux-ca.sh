#!/bin/sh
# Source this file; keep CA settings local to the installer process and its children.
fcc_ca_bundle=${FCC_CA_BUNDLE:-${PREFIX:?PREFIX is required}/etc/tls/cert.pem}
if [ ! -r "$fcc_ca_bundle" ] || [ ! -s "$fcc_ca_bundle" ]; then
    printf 'error: CA bundle missing or unreadable: %s\nInstall/reinstall ca-certificates in TermiNow, or set FCC_CA_BUNDLE to a trusted CA bundle.\n' "$fcc_ca_bundle" >&2
    return 1
fi
export CARGO_HTTP_CAINFO="$fcc_ca_bundle"
export CARGO_HTTP_PROXY_CAINFO="$fcc_ca_bundle"
export SSL_CERT_FILE="$fcc_ca_bundle"
export REQUESTS_CA_BUNDLE="$fcc_ca_bundle"
export CURL_CA_BUNDLE="$fcc_ca_bundle"
export PIP_CERT="$fcc_ca_bundle"
export GIT_SSL_CAINFO="$fcc_ca_bundle"
export CARGO_HTTP_SSL_VERIFY=true
