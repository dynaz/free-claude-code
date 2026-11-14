"""Isolated profile checks; runnable without importing the server's dependencies."""

import importlib.util
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profile_preserves_upstream_and_stages_lean_metadata(tmp_path):
    builder = load_file("termux_builder", ROOT / "scripts/build_termux.py")
    before = (ROOT / "pyproject.toml").read_bytes()
    builder.stage_project(tmp_path / "profile")
    staged = tmp_path / "profile"
    project = tomllib.loads((staged / "pyproject.toml").read_text())["project"]
    names = {builder.dependency_name(dep) for dep in project["dependencies"]}
    assert not names.intersection(builder.OMITTED)
    assert "fastapi" in project["dependencies"][2]
    assert project["requires-python"] == ">=3.14,<3.15"
    assert "fcc-termux" in project["scripts"]
    assert "gui-scripts" not in project
    assert (staged / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
    assert (ROOT / "pyproject.toml").read_bytes() == before
    assert (staged / "src/free_claude_code/core/data/cl100k_base.tiktoken").is_file()


def test_config_directory_must_be_absolute(monkeypatch, tmp_path):
    paths = load_file("termux_paths", ROOT / "src/free_claude_code/config/paths.py")
    monkeypatch.setenv("FCC_CONFIG_DIR", str(tmp_path))
    assert paths.config_dir_path() == tmp_path
    monkeypatch.setenv("FCC_CONFIG_DIR", "relative")
    import pytest

    with pytest.raises(ValueError, match="absolute"):
        paths.config_dir_path()
    monkeypatch.delenv("FCC_CONFIG_DIR")
    assert paths.config_dir_path() == Path.home() / ".fcc"


def test_installer_rejects_missing_prefix(tmp_path):
    env = {key: value for key, value in os.environ.items() if key != "PREFIX"}
    result = subprocess.run(
        ["sh", str(ROOT / "scripts/install-termux.sh")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "PREFIX" in result.stderr
    assert not list(tmp_path.iterdir())


def test_status_does_not_accept_an_unrelated_local_service():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"running"}')

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "src/free_claude_code/cli/termux.py"),
                "status",
                "--port",
                str(server.server_port),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not an FCC server" in result.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_foreground_launcher_applies_local_mobile_defaults(monkeypatch):
    import types

    launcher = load_file("termux_launcher", ROOT / "src/free_claude_code/cli/termux.py")
    calls = []
    stub = types.ModuleType("free_claude_code.cli.entrypoints")
    stub.serve = lambda argv: calls.append(argv)
    monkeypatch.setitem(sys.modules, "free_claude_code.cli.entrypoints", stub)
    for key in ("HOST", "PORT", "FCC_OPEN_BROWSER", "MESSAGING_PLATFORM", "FCC_TERMUX"):
        monkeypatch.setenv(key, "old-value")
    launcher.main(["serve", "--port", "8083"])
    assert calls == [[]]
    assert os.environ["HOST"] == "127.0.0.1"
    assert os.environ["PORT"] == "8083"
    assert os.environ["FCC_OPEN_BROWSER"] == "false"
    assert os.environ["MESSAGING_PLATFORM"] == "none"
    assert os.environ["FCC_TERMUX"] == "1"


def test_staging_refuses_to_overwrite_files(tmp_path):
    import pytest

    builder = load_file("termux_builder_guard", ROOT / "scripts/build_termux.py")
    sentinel = tmp_path / "pyproject.toml"
    sentinel.write_text("existing project")
    with pytest.raises(ValueError, match="empty"):
        builder.stage_project(tmp_path)
    assert sentinel.read_text() == "existing project"
