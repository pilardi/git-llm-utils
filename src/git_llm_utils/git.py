from enum import Enum
from pathlib import Path
from git_llm_utils.utils import execute_command, execute_raw_command, ErrorHandler
from typing import Optional, Tuple

import sys
import tempfile

_VALID_EXIT_CODES = [0]
COMMIT_MESSAGE_TEMPLATE = "commit-msg.template"


class Scope(Enum):
    GLOBAL = "global"  # use global config fil
    SYSTEM = "system"  # use system config file
    LOCAL = "local"  # use repository config file


def get_config(
    key: str,
    default_value: str | None = None,
    repository: Optional[str | Path] = None,
    scope: Optional[Scope] = None,
    abort_on_error: bool = False,
    namespace: str = "git-llm-utils",
    valid_codes=_VALID_EXIT_CODES,
) -> Optional[str]:
    output = execute_command(
        scope is not None
        and ["git", "config", "--get", f"--{scope.value}", f"{namespace}.{key}"]
        or ["git", "config", "--get", f"{namespace}.{key}"],
        cwd=repository,
        abort_on_error=abort_on_error,
        valid_codes=valid_codes,
    )
    return output and str.strip(output) or default_value


def set_config(
    key: str,
    value: str,
    scope: Scope = Scope.LOCAL,
    repository: Optional[str | Path] = None,
    abort_on_error: bool = True,
    namespace: str = "git-llm-utils",
    valid_codes=_VALID_EXIT_CODES,
):
    execute_command(
        [
            "git",
            "config",
            f"--{scope.value}",
            "--replace-all",
            f"{namespace}.{key}",
            f"{value}",
        ],
        cwd=repository,
        abort_on_error=abort_on_error,
        valid_codes=valid_codes,
    )


def unset_config(
    key: str,
    scope: Scope = Scope.LOCAL,
    abort_on_error: bool = True,
    repository: Optional[str | Path] = None,
):
    execute_command(
        ["git", "config", f"--{scope.value}", "--unset", f"git-llm-utils.{key}"],
        cwd=repository,
        abort_on_error=abort_on_error,
        valid_codes=_VALID_EXIT_CODES,
    )


def get_staged_changes(
    repository: Optional[str | Path] = None, abort_on_error: bool = True
) -> Optional[str]:
    """
    Generate diff message from the staged changes
    Returns:
        Optional[str]: the changes or empty if there weren't any
    """
    return execute_command(
        ["git", "diff", "--staged", "."],
        cwd=repository,
        abort_on_error=abort_on_error,
        valid_codes=_VALID_EXIT_CODES,
    )


def get_repository_path(
    repository: Optional[str | Path] = None, abort_on_error: bool = True
) -> Optional[Path]:
    repository_path = None
    if not repository:
        repository_path = execute_command(
            ["git", "rev-parse", "--show-toplevel"], abort_on_error=abort_on_error
        )
    else:
        rp = Path(repository)
        if rp.exists() and rp.is_dir():
            repository_path = execute_command(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=repository,
                abort_on_error=abort_on_error,
            )

    if repository and not repository_path:
        print(f"No git repository detected in the {repository} folder", file=sys.stderr)
        sys.exit(-1)

    return repository_path and Path(str(repository_path).strip()) or None


def get_repository_changes(
    repository: Optional[str | Path] = None, abort_on_error: bool = True
) -> Tuple[str | None, str | None]:
    branch = execute_command(["git", "branch", "--show-current"], cwd=repository)
    changeset = execute_command(["git", "status", "--porcelain"], cwd=repository)
    return branch, changeset


def request_message_edit(
    message: str,
    editor: str,
    repository: Optional[str | Path] = None,
    abort_on_error: bool = True,
) -> str | None:
    file = tempfile.NamedTemporaryFile()
    file.write("\n".encode())
    file.write(message.encode())
    (branch, changeset) = get_repository_changes(
        repository=repository, abort_on_error=abort_on_error
    )
    if branch is not None and changeset is not None:
        branch = branch.strip()
        commit_msg_template_path = (Path.cwd() / __file__).with_name(
            COMMIT_MESSAGE_TEMPLATE
        )
        for line in open(commit_msg_template_path):
            file.write(line.replace("{BRANCH}", branch).encode())
        for change in changeset.split("\n"):
            file.write(f"# \t{change}\n".encode())
        file.flush()
        execute_raw_command([editor, file.name])
        file.seek(0)
        lines = [
            s_line
            for line in file.readlines()
            if not (s_line := line.decode().strip()).startswith("#") and len(s_line) > 0
        ]
        ErrorHandler.report_debug(f"message update lines are: {lines}")
        if len(lines) > 0:
            return "\n".join(lines)

    return None
