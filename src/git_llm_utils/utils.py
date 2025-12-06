from pathlib import Path
from typing import Dict, Optional

import git_llm_utils
import os
import subprocess
import sys
import tomllib


def _bool(value: str) -> bool:
    return value and value.lower() in ("1", "true", "yes") or False


VERBOSE = _bool(os.environ.get("verbose", ""))


def report_error(message: str, *args, **kwargs):
    if VERBOSE:
        print(message, file=sys.stderr, *args, **kwargs)


def execute_command(
    command: list[str], abort_on_error: bool = True, verbose: bool = VERBOSE
) -> str | None:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            encoding="utf-8",
            errors="replace",
        )
        return process.stdout
    except subprocess.CalledProcessError as e:
        if abort_on_error:
            raise Exception(f"Failed to execute git command: {command}", e)
        report_error(f"Failed to execute git command: {command} -> {e}")
    return None


def get_tomlib_project() -> Dict:
    try:
        with open(Path("pyproject.toml"), mode="rb") as f:
            data = tomllib.load(f)
        return data["project"]
    except Exception as e:
        report_error(f"failed to read pyprojectL {e}")
        return {}


def read_file(file_path: Path | None) -> Optional[str]:
    if file_path is not None and file_path.exists():
        try:
            with open(file_path, "r") as file:
                return file.read()
        except Exception as e:
            report_error(f"Failed to read {file_path}: {e}")
    else:
        report_error(f"File {file_path} does not exist")
    return None


def read_version() -> str:
    try:
        return git_llm_utils.__version__
    except Exception as e:
        report_error(f"Failed to get version {e}")
        return "undefined"
