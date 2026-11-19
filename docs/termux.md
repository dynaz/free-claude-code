# TermiNow / native Termux aarch64 (experimental)

This fork adds a separate Android installation profile. It runs the existing FCC
HTTP proxy and Admin UI in native Termux; Ubuntu/proot and root are not required.
It is **not yet verified on a physical Android device**. A successful Linux wheel
build is not evidence of Android ABI compatibility.

## Requirements

- Native Android aarch64 TermiNow/Termux Python **3.14.x**. Upstream uses Python
  3.14 syntax. Changing a version constraint does not make Python 3.12/3.13 work.
- A package repository/bootstrap built for **your app's package name and PREFIX**.
  Do not copy official Termux binaries into another Android app's data directory.
- `git`, `python`, `python-pip`, `clang`, `rust`, `make`, `pkg-config`, `openssl`, `libffi` and development
  libraries required by native dependencies. On a compatible package repository:

```sh
pkg update
pkg install git python python-pip clang rust make pkg-config openssl libffi
python --version
```

If that repository does not provide Python 3.14, build/package that runtime for
TermiNow first, or use the upstream Ubuntu installation route. This installer
will stop rather than download a glibc Python runtime into Android.

## Install from this fork

Use app-private storage, not `/sdcard`. Before merge, check out the feature branch:

```sh
cd "$HOME"
git clone --branch terminow/termux-aarch64 https://github.com/dynaz/free-claude-code.git
cd free-claude-code
sh scripts/install-termux.sh
```

This creates `$HOME/.local/share/fcc-termux/venv`, retaining the app's PREFIX.
Native dependencies such as `pydantic-core`, `aiohttp`, and `sqlalchemy` still
need compatible Android wheels or local compilation. No Linux ARM64 wheel is
assumed to be an Android wheel. Installation errors must be resolved before
claiming device support. The installer does not upgrade the app's system pip.
For another Python command or isolated environment path, set `FCC_PYTHON` or
`FCC_TERMUX_VENV`. Existing environments are preserved; choose a new path for an
upgrade, validate it, then switch the app launcher to that path.

## Run and configure

```sh
FCC="$HOME/.local/share/fcc-termux/venv/bin/fcc-termux"
"$FCC" doctor
"$FCC" serve
```

Open `http://127.0.0.1:8082/admin` in the phone's browser. Configure a provider's
API key and model there. Free quota is controlled by the selected provider;
this fork does not provide free Anthropic credits or bundle shared API keys.
In a second session, check `fcc-termux status` using its full path above.
Use `--port 8083` on both `serve` and `status` if 8082 is occupied.

The launcher binds to `127.0.0.1`, disables automatic desktop browser opening,
and selects asyncio/h11 rather than optional Linux event-loop extensions.
Stop it with Ctrl+C. TermiNow should supervise this foreground process using its
existing terminal/service lifecycle; no background daemon, startup hook, or
Android foreground service is installed by this repository.

Configuration defaults to `$HOME/.fcc`, including logs under `logs/`. An app can
set **FCC_CONFIG_DIR to an absolute app-private path** on every server/client
invocation to isolate its configuration. It does not change HOME. Keep existing
`.fcc` data intact and back it up before moving it. Bind-to-loopback does not
isolate against other local Android apps; enable FCC Proxy Authentication when
using the proxy and use the upstream Admin protection mechanisms.

## Profile boundaries

The lean build omits desktop launchers, the upstream updater command, local
voice, Riva/gRPC, Copilot SDK, Telegram/Discord packages and tiktoken. Messaging is
disabled by the Termux launcher. Do not enable absent integrations in Admin.
NVIDIA NIM **text** requests remain available; Riva voice is a separate feature.
FCC's existing token-estimation fallback is used when tiktoken is absent, so
counts are approximate.

Coding agents are separate installations. The included `fcc-claude`, `fcc-codex`
and other launcher entry points do not guarantee their client binaries run on
Android. Validate a client on TermiNow first, then connect it to FCC. The generic
OpenAI-compatible endpoint is `http://127.0.0.1:8082/v1`. Use the configured proxy
token if authentication is enabled.

## Build and validate

The helper stages a separate pyproject, leaving upstream pyproject/uv.lock intact:

```sh
python -m pip install build
python scripts/build_termux.py --out-dir dist/termux
# Or inspect and install a staged profile:
python scripts/build_termux.py --stage /absolute/path/to/new-stage
```

A pure-Python FCC wheel does not include compiled dependencies. For an offline
Android release, build a complete dependency wheelhouse against the exact
TermiNow Python ABI, Android API level, and PREFIX; test installation on-device.
The profile version includes its source commit. Do not run the upstream updater
on this installation: it can replace this profile with the desktop dependency set.

Before promoting this profile: verify clean install, Admin load, provider/model
setup, a real streaming/tool-call request, stop/restart, port conflict, and app
background/resume on Android aarch64. This repository does not contain TermiNow's
Android UI or bootstrap source, so those integrations are not implemented here.

The upstream AGPL-3.0 license and notices are retained in the staged wheel.

## Recover from a Cargo / maturin certificate error

If the build reports `unable to get local issuer certificate` while fetching
crates.io, repair the native CA bundle first. The installer now exports the
app-prefix bundle consistently to Cargo, pip/Python, Requests, curl and Git;
Cargo build subprocesses inherit it. TLS verification stays enabled.

```sh
pkg install ca-certificates curl
pkg reinstall ca-certificates
export FCC_CA_BUNDLE="$PREFIX/etc/tls/cert.pem"
# From an updated checkout containing the CA/resume fix:
sh scripts/install-termux.sh --resume
```

`--resume` reuses a compatible existing Python 3.14 virtualenv and retries pip
installation; it never removes the environment or credentials. An incompatible
or broken interpreter is rejected. The default invocation still refuses to
replace an existing environment. A TLS preflight against the crates.io index
runs before any environment changes. A failing preflight can also mean a
network/proxy trust problem; use an appropriately trusted bundle via
`FCC_CA_BUNDLE`, rather than disabling certificate checks.

Fixing the CA error addresses the failure shown in that log. Further Android
native compilation failures may still require separate changes.

## Recover from openssl-sys not finding OpenSSL

A later build can pass the CA check and fail in `openssl-sys` with an OpenSSL
location error. For native Android, use the app's OpenSSL headers and libraries
under `$PREFIX`, rather than Ubuntu's `/usr` paths. Install/reinstall `openssl`
and ensure `pkg-config`, `clang`, `rust` and `libffi` are installed.

The installer now sources `scripts/termux-native.sh` before any pip build. It
checks the headers and shared libraries, exports `OPENSSL_DIR`,
`OPENSSL_INCLUDE_DIR`, `OPENSSL_LIB_DIR`, `OPENSSL_NO_VENDOR` and the native
Android target-prefixed equivalents, and prepends the app's pkg-config paths
while retaining existing paths. Pip build isolation inherits these environment
variables. Missing inputs fail before network requests or virtualenv changes.
Retry with `--resume` after repairing the package. This fixes OpenSSL discovery;
it does not establish that the complete Android build has passed.
