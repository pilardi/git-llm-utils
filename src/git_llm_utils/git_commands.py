from enum import Enum
from typing import Optional
from git_llm_utils.utils import execute_command

_VALID_EXIT_CODES = [0, 1]


class Scope(Enum):
    GLOBAL = "global"  # use global config fil
    SYSTEM = "system"  # use system config file
    LOCAL = "local"  # use repository config file


def get_config(
    key: str,
    default_value: str | None = None,
    scope: Scope = Scope.LOCAL,
    abort_on_error: bool = False,
) -> Optional[str]:
    output = execute_command(
        ["git", "config", "--get", f"--{scope.value}", f"git-llm-utils.{key}"],
        abort_on_error=abort_on_error,
        valid_codes=_VALID_EXIT_CODES,
    )
    return output and str.strip(output) or default_value


def set_config(
    key: str, value: str, scope: Scope = Scope.LOCAL, abort_on_error: bool = True
):
    execute_command(
        [
            "git",
            "config",
            f"--{scope.value}",
            "--replace-all",
            f"git-llm-utils.{key}",
            f"{value}",
        ],
        abort_on_error=abort_on_error,
        valid_codes=_VALID_EXIT_CODES,
    )


def unset_config(key: str, scope: Scope = Scope.LOCAL, abort_on_error: bool = True):
    execute_command(
        ["git", "config", f"--{scope.value}", "--unset", f"git-llm-utils.{key}"],
        abort_on_error=abort_on_error,
        valid_codes=_VALID_EXIT_CODES,
    )


def get_staged_changes(folder: str, abort_on_error: bool = True) -> Optional[str]:
    """
    Generate diff message from the staged changes
    Returns:
        Optional[str]: the changes or empty if there weren't any
    """
    return execute_command(
        ["git", "diff", "--staged", folder],
        abort_on_error=abort_on_error,
        valid_codes=_VALID_EXIT_CODES,
    )
