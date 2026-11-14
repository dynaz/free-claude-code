"""Foreground launcher and local diagnostics for the experimental Termux profile."""

import argparse
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

REQUIRED_MODULES = (
    "fastapi",
    "uvicorn",
    "pydantic_core",
    "httpx",
    "httpx2",
    "sqlalchemy",
)


def diagnostics() -> dict[str, object]:
    """Inspect prerequisites without importing native extensions or exposing secrets."""
    return {
        "python": platform.python_version(),
        "python_supported": (3, 14) <= sys.version_info[:2] < (3, 15),
        "architecture": platform.machine(),
        "android_python": sys.platform == "android"
        or hasattr(sys, "getandroidapilevel"),
        "prefix": os.environ.get("PREFIX", ""),
        "config_dir": str(
            Path(os.environ.get("FCC_CONFIG_DIR", str(Path.home() / ".fcc")))
        ),
        "missing_modules": [
            name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None
        ],
        "profile": "experimental-termux",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "status", "doctor"))
    parser.add_argument("--port", type=int, default=8082)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.command == "doctor":
        report = diagnostics()
        print(json.dumps(report, indent=2))
        raise SystemExit(
            0 if report["python_supported"] and not report["missing_modules"] else 1
        )
    if args.command == "status":
        # Ignore inherited proxy settings for a strictly local health request.
        try:
            opener = build_opener(ProxyHandler({}))
            with opener.open(
                f"http://127.0.0.1:{args.port}/admin/api/status", timeout=3
            ) as response:
                status = json.load(response)
            if (
                not isinstance(status, dict)
                or not isinstance(status.get("instance_id"), str)
                or len(status["instance_id"]) != 32
            ):
                raise ValueError("endpoint is not an FCC server")
            print(json.dumps({"status": status.get("status"), "port": args.port}))
        except (URLError, OSError, ValueError) as exc:
            print(f"FCC unavailable: {exc}", file=sys.stderr)
            raise SystemExit(1) from None
        return
    if not (3, 14) <= sys.version_info[:2] < (3, 15):
        parser.error(
            "this source requires Python 3.14; use a matching TermiNow Python package"
        )
    # The app owns the foreground process; Ctrl+C or app termination stops it.
    os.environ.update(
        {
            "HOST": "127.0.0.1",
            "PORT": str(args.port),
            "FCC_OPEN_BROWSER": "false",
            "MESSAGING_PLATFORM": "none",
            "FCC_TERMUX": "1",
        }
    )
    from free_claude_code.cli.entrypoints import serve

    print(f"FCC Admin: http://127.0.0.1:{args.port}/admin", flush=True)
    serve([])


if __name__ == "__main__":
    main()
