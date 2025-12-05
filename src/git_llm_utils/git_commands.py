from enum import Enum
from typing import Optional, Tuple

import os
import subprocess
import sys


class Scope(Enum):
    GLOBAL = "--global"  # use global config fil
    SYSTEM = "--system"  # use system config file
    LOCAL = "--local"  # use repository config file


def _bool(value: str) -> bool:
    return value and value.lower() in ("1", "true", "yes") or False


def get_default_setting(
    setting: str, default: str | None, flag: bool = False, help: str | None = None
):
    value = get_config(setting, default)
    return (
        setting,
        flag,
        flag and str(_bool(value)) or value,  # type: ignore
        flag and str(_bool(default)) or default,  # type: ignore
        help,
    )


def _execute_command(command: list[str]) -> Tuple[str, Optional[str]]:
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
        return process.stdout, None
    except subprocess.CalledProcessError as e:
        return None, e.stderr  # type: ignore


def get_config(key: str, default_value: str | None = None) -> Optional[str]:
    output, _ = _execute_command(["git", "config", "--get", f"git-llm-utils.{key}"])
    return output and str.strip(output) or default_value


def set_config(key: str, value: str, scope: Scope = Scope.LOCAL):
    output, error = _execute_command(
        [
            "git",
            "config",
            f"{scope.value}",
            "--replace-all",
            f"git-llm-utils.{key}",
            f"{value}",
        ]
    )
    if error:
        print(f"Failed to set {key} config: {error}", file=sys.stderr)


def unset_config(key: str, scope: Scope = Scope.LOCAL):
    output, error = _execute_command(
        ["git", "config", f"{scope.value}", "--unset", f"git-llm-utils.{key}"]
    )
    if error:
        print(f"Failed to set {key} config: {error}", file=sys.stderr)


def get_staged_changes(folder: str, abort_on_error: bool = True) -> Optional[str]:
    """
    Generate diff message from the staged changes
    Returns:
        Optional[str]: the changes or empty if there weren't any
    """
    output, error = _execute_command(["git", "diff", "--staged", folder])
    if abort_on_error and error:
        raise Exception(f"Failed to execute git command: {error}")
    return output
