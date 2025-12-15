from pathlib import Path
from typing import Dict, Iterable, Optional

import git_llm_utils
import os
import subprocess
import sys
import tomllib


def _bool(value: str) -> bool:
    return value and value.lower() in ("1", "true", "yes") or False


GIT_LLM_UTILS_DEBUG = "GIT_LLM_UTILS_DEBUG"
DEBUG = _bool(os.environ.get(GIT_LLM_UTILS_DEBUG, ""))


def report_error(message: str, debug: bool = DEBUG, *args, **kwargs):
    if debug:
        print(message, file=sys.stderr, *args, **kwargs)


def execute_background_command(
    command: list[str],
    abort_on_error: bool = True,
    cwd: str | None = None,
    verbose: bool = DEBUG,
) -> subprocess.Popen | None:
    try:
        return subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
    except subprocess.CalledProcessError as e:
        if abort_on_error:
            raise Exception(f"Failed to execute background command: {command}", e)
        report_error(
            f"Failed to execute background command: {command} -> {e}", debug=verbose
        )
    return None


def execute_command(
    command: list[str],
    abort_on_error: bool = True,
    cwd: str | None = None,
    verbose: bool = DEBUG,
    valid_codes: Iterable[int] = [0],
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
            cwd=cwd,
        )
        return process.stdout
    except subprocess.CalledProcessError as e:
        if e.returncode not in valid_codes:
            if abort_on_error:
                raise Exception(f"Failed to execute command: {command}", e)
            report_error(f"Failed to execute command: {command} -> {e}", debug=verbose)
    return None


def get_tomlib_project() -> Dict:
    try:
        with open(Path("pyproject.toml"), mode="rb") as f:
            data = tomllib.load(f)
        return data["project"]
    except Exception as e:
        report_error(f"failed to read pyprojectL {e}")
        return {}


def read_file(file_path: Path | None, debug: bool = DEBUG) -> Optional[str]:
    if file_path is not None and file_path.exists():
        try:
            with open(file_path, "r") as file:
                return file.read()
        except Exception as e:
            report_error(f"Failed to read {file_path}: {e}", debug=debug)
    else:
        report_error(f"File {file_path} does not exist", debug=debug)
    return None


def write_file(
    file_path: Path, content: str = "", overwrite: bool = False, debug: bool = DEBUG
) -> bool:
    if not file_path.exists() or overwrite:
        try:
            with open(file_path, "w") as file:
                file.write(content)
                return True
        except Exception as e:
            report_error(f"Failed to write {file_path}: {e}", debug=debug)
    else:
        report_error(
            f"File {file_path} already exist, use overwrite if needed", debug=debug
        )
    return False


def read_version() -> str:
    try:
        return git_llm_utils.__version__
    except Exception as e:
        report_error(f"Failed to get version {e}")
        return "undefined"
