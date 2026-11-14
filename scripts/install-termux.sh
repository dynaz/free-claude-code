#!/bin/sh
# Run from a checkout inside TermiNow/Termux, never from Ubuntu/proot.
set -eu
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
[ "${1:-}" != "--help" ] || {
    printf 'Usage: sh scripts/install-termux.sh\nRequires native Termux aarch64, PREFIX, Python 3.14, clang, rust, make, pkg-config.\n'
    exit 0
}
[ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ] || fail 'Run inside TermiNow/Termux with its own PREFIX.'
[ "$(uname -m)" = aarch64 ] || fail 'This experimental installer targets aarch64 only.'
python_bin=${FCC_PYTHON:-python}
command -v "$python_bin" >/dev/null 2>&1 || fail 'Install the TermiNow Python package first.'
"$python_bin" -c 'import sys; sys.exit(0 if sys.platform == "android" or hasattr(sys, "getandroidapilevel") else 1)' || fail 'Native Android Python required; do not use a glibc Linux Python binary.'
"$python_bin" -c 'import sys; sys.exit(0 if (3,14) <= sys.version_info[:2] < (3,15) else 1)' || fail 'Python 3.14 required. Do not lower the version check; the code uses Python 3.14 syntax.'
for tool in clang cargo make pkg-config; do
    command -v "$tool" >/dev/null 2>&1 || fail "Missing $tool. Install clang rust make pkg-config using the app package manager."
done
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
venv_dir=${FCC_TERMUX_VENV:-$HOME/.local/share/fcc-termux/venv}
[ ! -e "$venv_dir" ] || fail "Environment already exists at $venv_dir. Preserve it or choose FCC_TERMUX_VENV for a new install."
umask 077
"$python_bin" -m venv "$venv_dir"
venv_python=$venv_dir/bin/python
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
