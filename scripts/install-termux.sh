#!/bin/sh
# Run from a checkout inside TermiNow/Termux, never from Ubuntu/proot.
set -eu
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
resume=0
case "${1:-}" in
    "") ;;
    --resume) resume=1 ;;
    --help)
        printf 'Usage: sh scripts/install-termux.sh [--resume]\nRequires native Termux aarch64, PREFIX, Python 3.14, ca-certificates, curl, clang, rust, make, pkg-config.\n'
        exit 0 ;;
    *) fail 'Unknown option; use --help.' ;;
esac
[ "$#" -le 1 ] || fail 'Too many arguments; use --help.'
[ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ] || fail 'Run inside TermiNow/Termux with its own PREFIX.'
[ "$(uname -m)" = aarch64 ] || fail 'This experimental installer targets aarch64 only.'
python_bin=${FCC_PYTHON:-python}
command -v "$python_bin" >/dev/null 2>&1 || fail 'Install the TermiNow Python package first.'
"$python_bin" -c 'import sys; sys.exit(0 if sys.platform == "android" or hasattr(sys, "getandroidapilevel") else 1)' || fail 'Native Android Python required; do not use a glibc Linux Python binary.'
"$python_bin" -c 'import sys; sys.exit(0 if (3,14) <= sys.version_info[:2] < (3,15) else 1)' || fail 'Python 3.14 required. Do not lower the version check; the code uses Python 3.14 syntax.'
for tool in clang cargo make pkg-config curl; do
    command -v "$tool" >/dev/null 2>&1 || fail "Missing $tool. Install clang rust make pkg-config curl using the app package manager."
done
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
# Resolve trust before creating an environment or starting nested pip/Cargo builds.
. "$source_dir/scripts/termux-ca.sh" || fail 'Could not configure trusted CA certificates.'
curl --fail --silent --show-error --connect-timeout 15 --max-time 30 \
    --cacert "$CARGO_HTTP_CAINFO" https://index.crates.io/config.json -o /dev/null || \
    fail 'Cannot verify crates.io TLS. Repair the CA bundle/network, then retry. No virtualenv was changed.'
venv_dir=${FCC_TERMUX_VENV:-$HOME/.local/share/fcc-termux/venv}
umask 077
venv_python=$venv_dir/bin/python
if [ -e "$venv_dir" ]; then
    [ "$resume" -eq 1 ] || fail "Environment already exists at $venv_dir. Use --resume to retry it without deleting files."
    [ -f "$venv_dir/pyvenv.cfg" ] && [ -x "$venv_python" ] || fail 'Existing path is not a usable Python virtualenv; preserve it and choose a new FCC_TERMUX_VENV.'
    "$venv_python" -c 'import os, sys; sys.exit(0 if (3,14) <= sys.version_info[:2] < (3,15) and os.path.realpath(sys.prefix) == os.path.realpath(sys.argv[1]) else 1)' "$venv_dir" || fail 'Existing virtualenv has an incompatible Python or prefix. Preserve it and choose a new FCC_TERMUX_VENV.'
else
    "$python_bin" -m venv "$venv_dir"
fi
# Keep builds in app-private storage; Android shared storage is not executable.
export TMPDIR=${TMPDIR:-$PREFIX/tmp}
mkdir -p "$TMPDIR"
"$venv_python" -m pip install build
stage_dir=$(mktemp -d "$TMPDIR/fcc-stage.XXXXXX")
trap 'rm -rf "$stage_dir"' EXIT HUP INT TERM
"$venv_python" "$source_dir/scripts/build_termux.py" --stage "$stage_dir"
"$venv_python" -m pip install "$stage_dir"
"$venv_dir/bin/fcc-termux" doctor
printf '\nInstalled experimental FCC profile. Run:\n  "%s/bin/fcc-termux" serve\n' "$venv_dir"
