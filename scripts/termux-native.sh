#!/bin/sh
# Source before pip so isolated maturin/Cargo builds inherit the app's OpenSSL layout.
fcc_native_prefix=${PREFIX:?PREFIX is required}
for fcc_native_file in include/openssl/ssl.h include/openssl/opensslv.h lib/libssl.so lib/libcrypto.so; do
    if [ ! -r "$fcc_native_prefix/$fcc_native_file" ]; then
        printf 'error: Missing native OpenSSL build input: %s\nInstall/reinstall openssl with the TermiNow package manager, then retry --resume.\n' "$fcc_native_prefix/$fcc_native_file" >&2
        return 1
    fi
done
export OPENSSL_DIR="$fcc_native_prefix"
export OPENSSL_INCLUDE_DIR="$fcc_native_prefix/include"
export OPENSSL_LIB_DIR="$fcc_native_prefix/lib"
export OPENSSL_NO_VENDOR=1
# openssl-sys gives target-specific variables precedence over generic ones.
export AARCH64_LINUX_ANDROID_OPENSSL_DIR="$OPENSSL_DIR"
export AARCH64_LINUX_ANDROID_OPENSSL_INCLUDE_DIR="$OPENSSL_INCLUDE_DIR"
export AARCH64_LINUX_ANDROID_OPENSSL_LIB_DIR="$OPENSSL_LIB_DIR"
export PKG_CONFIG_PATH="$fcc_native_prefix/lib/pkgconfig:$fcc_native_prefix/share/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
