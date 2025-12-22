from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import git_llm_utils
import os
import subprocess
import sys
import tomllib


def _bool(value: Optional[str | Any]) -> bool:
    if type(value) is bool:
        return value
    return value and value.lower() in ("1", "true", "yes") or False


class ErrorHandler:
    NO_GIT_REPOSITORY = -1
    INVALID_CLIENT = -2
    CLIENT_NOT_DETECTED = -3
    FILE_ALREADY_EXISTS = -4
    INVALID_HOOK_TEMPLATE = -5
    INVALID_SCOPE = -6
    UNDEFINED_ERROR = -7

    GIT_LLM_DEBUG = "GIT_LLM_DEBUG"
    debug = _bool(os.environ.get(GIT_LLM_DEBUG))

    @staticmethod
    def _report(
        message: str, file=sys.stderr, show: bool | None = None, *args, **kwargs
    ):
        if ErrorHandler.debug or show:
            print(message, file=file, *args, **kwargs)

    @staticmethod
    def report_error(message: str, show: bool | None = None, *args, **kwargs):
        ErrorHandler._report(f"ERROR: {message}", show=show, *args, **kwargs)

    @staticmethod
    def report_debug(message: str, show: bool | None = None, *args, **kwargs):
        ErrorHandler._report(f"DEBUG: {message}", show=show, *args, **kwargs)


def execute_background_command(
    command: list[str],
    abort_on_error: bool = True,
    cwd: str | None = None,
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
        ErrorHandler.report_error(
            f"Failed to execute background command: {command} -> {e}"
        )
    return None


def execute_command(
    command: list[str],
    abort_on_error: bool = True,
    cwd: Optional[str | Path] = None,
    valid_codes: Iterable[int] = [0],
) -> str | None:
    ErrorHandler.report_debug(f"Will run command: {command}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        if e.returncode not in valid_codes:
            if abort_on_error:
                raise Exception(f"Failed to execute command: {command}", e)
            ErrorHandler.report_error(f"Failed to execute command: {command} -> {e}")
    return None


def get_tomlib_project() -> Dict:
    try:
        with open(Path("pyproject.toml"), mode="rb") as f:
            data = tomllib.load(f)
        return data["project"]
    except Exception as e:
        ErrorHandler.report_error(f"failed to read pyproject {e}")
        return {}


def read_file(file_path: Path | None) -> Optional[str]:
    if file_path is not None and file_path.exists():
        try:
            with open(file_path, "r") as file:
                return file.read()
        except Exception as e:
            ErrorHandler.report_error(f"Failed to read {file_path}: {e}")
    else:
        ErrorHandler.report_error(f"File {file_path} does not exist")
    return None


def write_file(file_path: Path, content: str = "", overwrite: bool = False) -> bool:
    if not file_path.exists() or overwrite:
        try:
            with open(file_path, "w") as file:
                file.write(content)
                return True
        except Exception as e:
            ErrorHandler.report_error(f"Failed to write {file_path}: {e}")
    else:
        ErrorHandler.report_error(
            f"File {file_path} already exist, use overwrite if needed"
        )
    return False


def read_version() -> str:
    try:
        return git_llm_utils.__version__
    except Exception as e:
        ErrorHandler.report_error(f"Failed to get version {e}")
        return "undefined"
