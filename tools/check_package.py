"""Validate source and distributions, then test an installed wheel."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path = ROOT) -> None:
    """Run a check and stop immediately on failure."""
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir", type=Path,
        help="Copy validated distributions into this directory",
    )
    args = parser.parse_args()
    run(sys.executable, "-m", "pytest", "-q")
    run(sys.executable, "-m", "ruff", "check", "src", "tests", "tools")
    run(sys.executable, "-m", "mypy", "--strict", "src", "tools")

    with tempfile.TemporaryDirectory(prefix="tile-package-check-") as tmp:
        workspace = Path(tmp)
        distributions = workspace / "dist"
        run(
            sys.executable, "-m", "build", "--outdir", str(distributions)
        )
        artifacts = sorted(distributions.iterdir())
        wheel, = distributions.glob("*.whl")
        run(
            sys.executable, "-m", "twine", "check", "--strict",
            *(str(path) for path in artifacts),
        )
        run(
            sys.executable, "-m", "check_wheel_contents", str(wheel),
            "--package", str(ROOT / "src" / "tile_identity_resolver"),
        )

        # Do not inherit site packages or the repository's pytest config.
        environment = workspace / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        scripts = "Scripts" if os.name == "nt" else "bin"
        executable = "python.exe" if os.name == "nt" else "python"
        python = str(environment / scripts / executable)
        run(
            python, "-I", "-m", "pip", "install", f"{wheel}[test]",
            cwd=workspace,
        )
        shutil.copytree(ROOT / "tests", workspace / "tests")
        config = workspace / "pytest.ini"
        config.write_text("[pytest]\n", encoding="utf-8")
        run(
            python, "-I", "-m", "pytest", "-q", "-c", str(config),
            "--import-mode=importlib", "tests", cwd=workspace,
        )
        run(
            python, "-I", "-c",
            "from importlib.resources import files; "
            "assert files('tile_identity_resolver')"
            ".joinpath('py.typed').is_file()",
            cwd=workspace,
        )
        if args.dist_dir is not None:
            args.dist_dir.mkdir(parents=True, exist_ok=True)
            for artifact in artifacts:
                shutil.copy2(artifact, args.dist_dir / artifact.name)

    print("All package checks passed.")


if __name__ == "__main__":
    main()
