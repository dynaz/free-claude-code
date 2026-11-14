"""Build a separate, lean Android profile without changing upstream metadata/lock."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OMITTED = {
    "tiktoken",
    "python-telegram-bot",
    "discord.py",
    "github-copilot-sdk",
    "grpcio",
    "grpcio-tools",
    "nvidia-riva-client",
    "pystray",
    "Pillow",
}


def dependency_name(requirement: str) -> str:
    return requirement.split("[", 1)[0].split(">", 1)[0].split(";", 1)[0].strip()


def stage_project(destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Build staging directory must be empty")
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = metadata["project"]
    revision = subprocess.check_output(
        ["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True
    ).strip()
    project.pop("dynamic")
    project["version"] = f"0+terminow.{revision}"
    # Python 3.14 syntax is used throughout the source; never silently downgrade.
    project["requires-python"] = ">=3.14,<3.15"
    project["dependencies"] = [
        requirement.replace("fastapi[standard]", "fastapi")
        for requirement in project["dependencies"]
        if dependency_name(requirement) not in OMITTED
    ] + ["websockets>=15", "python-multipart>=0.0.20"]
    project.pop("gui-scripts", None)
    project.pop("optional-dependencies", None)
    project["scripts"].pop("_fcc-update-check", None)
    project["scripts"]["fcc-termux"] = "free_claude_code.cli.termux:main"
    sections = [
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"',
        "[project]",
    ]
    for key, value in project.items():
        if key != "scripts":
            sections.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    sections.append("[project.scripts]")
    sections.extend(
        f"{key} = {json.dumps(value)}" for key, value in project["scripts"].items()
    )
    sections.append(
        '[tool.hatch.build.targets.wheel]\npackages = ["src/free_claude_code"]'
    )
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "pyproject.toml").write_text("\n".join(sections) + "\n")
    shutil.copytree(
        ROOT / "src", destination / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    for name in ("README.md", "LICENSE"):
        shutil.copy2(ROOT / name, destination / name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", type=Path, help="Write an inspectable standalone build tree"
    )
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist" / "termux")
    args = parser.parse_args()
    if args.stage:
        stage_project(args.stage)
        return
    with tempfile.TemporaryDirectory(prefix="fcc-termux-") as temporary:
        stage = Path(temporary)
        stage_project(stage)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(args.out_dir.resolve()),
                str(stage),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
