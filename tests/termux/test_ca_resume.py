"""Installer recovery checks with simulated Android tools; no network or device needed."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def executable(path, text):
    path.write_text("#!/bin/sh\n" + text)
    path.chmod(0o700)


@pytest.fixture
def android(tmp_path):
    prefix = tmp_path / "app prefix"
    tools = prefix / "bin"
    tools.mkdir(parents=True)
    ca = prefix / "etc/tls/cert.pem"
    ca.parent.mkdir(parents=True)
    ca.write_text("trusted test bundle\n")
    for name in (
        "include/openssl/ssl.h",
        "include/openssl/opensslv.h",
        "lib/libssl.so",
        "lib/libcrypto.so",
    ):
        native_file = prefix / name
        native_file.parent.mkdir(parents=True, exist_ok=True)
        native_file.write_text("test native build input\n")

    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "actions.log"
    env = dict(
        os.environ,
        PREFIX=str(prefix),
        HOME=str(home),
        TMPDIR=str(prefix / "tmp"),
        PATH=f"{tools}:{os.environ['PATH']}",
        FCC_PYTHON=str(tools / "python"),
        ACTION_LOG=str(log),
        SSL_CERT_FILE="stale-root",
        CARGO_HTTP_CAINFO="stale-root",
    )
    env["OPENSSL_DIR"] = "stale-other-app-prefix"
    env["AARCH64_LINUX_ANDROID_OPENSSL_LIB_DIR"] = "stale-other-app-lib"
    env["PKG_CONFIG_PATH"] = "/keep/custom/pkgconfig"
    env.pop("FCC_CA_BUNDLE", None)
    env.pop("FCC_TERMUX_VENV", None)
    executable(tools / "uname", "echo aarch64\n")
    executable(tools / "python", "exit 0\n")
    for name in ("clang", "cargo", "make", "pkg-config"):
        executable(tools / name, "exit 0\n")
    executable(
        tools / "curl",
        'echo "tls:$CARGO_HTTP_CAINFO" >> "$ACTION_LOG"\nexit "${TLS_EXIT:-0}"\n',
    )
    return env, home, ca, log


def run_installer(env, *args):
    return subprocess.run(
        ["sh", str(ROOT / "scripts/install-termux.sh"), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def existing_environment(home):
    venv = home / ".local/share/fcc-termux/venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = test\n")
    executable(
        venv / "bin/python",
        """if [ "$1" = -c ]; then exit "${INVALID_VENV:-0}"; fi
printf 'native:%s|%s|%s|%s|%s|%s\\n' "$OPENSSL_DIR" "$OPENSSL_LIB_DIR" "$OPENSSL_INCLUDE_DIR" "$OPENSSL_NO_VENDOR" "$AARCH64_LINUX_ANDROID_OPENSSL_LIB_DIR" "$PKG_CONFIG_PATH" >> "$ACTION_LOG"
printf 'python:%s|%s|%s|%s|%s|%s\\n' "$*" "$CARGO_HTTP_CAINFO" "$SSL_CERT_FILE" "$PIP_CERT" "$CARGO_HTTP_SSL_VERIFY" "$REQUESTS_CA_BUNDLE" >> "$ACTION_LOG"
""",
    )
    executable(venv / "bin/fcc-termux", 'echo "doctor:$*" >> "$ACTION_LOG"\n')
    sentinel = venv / "keep-me"
    sentinel.write_text("existing data")
    return venv, sentinel


def test_resume_propagates_ca_into_nested_builds_without_deleting_data(android):
    env, home, ca, log = android
    _, sentinel = existing_environment(home)
    result = run_installer(env, "--resume")
    assert result.returncode == 0, result.stderr
    assert sentinel.read_text() == "existing data"
    lines = log.read_text().splitlines()
    assert lines[0] == f"tls:{ca}"
    builds = [line for line in lines if line.startswith("python:")]
    assert builds
    assert all(line.endswith(f"|{ca}|{ca}|{ca}|true|{ca}") for line in builds)
    assert "doctor:doctor" in lines
    prefix = Path(env["PREFIX"])
    native = [line for line in lines if line.startswith("native:")]
    assert native
    expected = f"native:{prefix}|{prefix}/lib|{prefix}/include|1|{prefix}/lib|{prefix}/lib/pkgconfig:{prefix}/share/pkgconfig:/keep/custom/pkgconfig"
    assert all(line == expected for line in native)


def test_default_still_refuses_existing_environment(android):
    env, home, _, log = android
    _, sentinel = existing_environment(home)
    result = run_installer(env)
    assert result.returncode != 0
    assert "--resume" in result.stderr
    assert "python:" not in log.read_text()
    assert sentinel.read_text() == "existing data"


def test_tls_failure_prevents_environment_changes(android):
    env, home, _, log = android
    env["TLS_EXIT"] = "60"
    result = run_installer(env, "--resume")
    assert result.returncode != 0
    assert "Cannot verify crates.io TLS" in result.stderr
    assert not (home / ".local").exists()
    assert "python:" not in log.read_text()


def test_missing_ca_fails_before_network(android):
    env, _, ca, log = android
    ca.unlink()
    result = run_installer(env, "--resume")
    assert result.returncode != 0
    assert "ca-certificates" in result.stderr
    assert not log.exists()


def test_custom_ca_bundle_is_used(android):
    env, home, ca, log = android
    custom = ca.parent / "private root.pem"
    custom.write_text("custom trust\n")
    env["FCC_CA_BUNDLE"] = str(custom)
    existing_environment(home)
    result = run_installer(env, "--resume")
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines()[0] == f"tls:{custom}"


def test_incompatible_venv_is_preserved(android):
    env, home, _, log = android
    _, sentinel = existing_environment(home)
    env["INVALID_VENV"] = "1"
    result = run_installer(env, "--resume")
    assert result.returncode != 0
    assert "incompatible Python" in result.stderr
    assert sentinel.read_text() == "existing data"
    assert "python:" not in log.read_text()


def test_missing_openssl_header_stops_before_network_or_env_changes(android):
    env, home, _, log = android
    (Path(env["PREFIX"]) / "include/openssl/ssl.h").unlink()
    result = run_installer(env, "--resume")
    assert result.returncode != 0
    assert "Missing native OpenSSL build input" in result.stderr
    assert not log.exists()
    assert not (home / ".local").exists()


def test_missing_openssl_library_preserves_partial_venv(android):
    env, home, _, log = android
    _, sentinel = existing_environment(home)
    (Path(env["PREFIX"]) / "lib/libcrypto.so").unlink()
    result = run_installer(env, "--resume")
    assert result.returncode != 0
    assert "libcrypto.so" in result.stderr
    assert sentinel.read_text() == "existing data"
    assert not log.exists()
