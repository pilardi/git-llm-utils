from enum import Enum
from git_llm_utils.git_commands import (
    get_config as _get_config,
    get_staged_changes,
    set_config as _set_config,
    unset_config,
    Scope,
)
from git_llm_utils.llm_cli import LLMClient
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version as _import_version
from typing import Any, Dict, Optional, TextIO

import sys
import tomllib
import typer


def _get_tomlib_project() -> Dict:
    try:
        with open(Path("pyproject.toml"), mode="rb") as f:
            data = tomllib.load(f)
        return data["project"]
    except Exception:
        pass
    return {}


def _get_version(show: bool):
    if show:
        try:
            v = _import_version("git_llm_utils")
        except PackageNotFoundError:
            v = "undefined"
        print(f"Version is {v}")
        raise typer.Exit()


def _get_description(file_path: Path | None) -> Optional[str]:
    if file_path is not None and file_path.exists():
        with open(file_path, "r") as file:
            return file.read()
    else:
        print(f"Description file {file_path} does not exist", file=sys.stderr)
    return None


def _bool(value: str) -> bool:
    return value and value.lower() in ("1", "true", "yes") or False


def _get_default_setting(setting: str, default: str | None, flag: bool = True):
    value = _get_config(setting, default)
    return (
        setting,
        flag,
        flag and _bool(value) or value,  # type: ignore
        flag and _bool(default) or default,  # type: ignore
    )


class Setting(Enum):
    def __new__(cls, value, flag: bool, default: Any | None, factory: Any | None):
        enum = object.__new__(cls)
        enum._value_ = value
        enum.flag = flag  # type: ignore
        enum.default = default  # type: ignore
        enum.factory = factory  # type: ignore
        return enum

    EMOJIS = _get_default_setting("emojis", "True", flag=True)
    COMMENTS = _get_default_setting("comments", "True", flag=True)
    MODEL = _get_default_setting("model", "ollama/qwen3-coder:480b-cloud")
    API_KEY = _get_default_setting("api_key", None)
    API_URL = _get_default_setting("api_url", None)
    DESCRIPTION_FILE = _get_default_setting("description_file", "README.md")
    USE_TOOLS = _get_default_setting("use_tools", "False", flag=True)
    MANUAL = _get_default_setting("manual", "True", flag=True)


app = typer.Typer(help=_get_tomlib_project().get("description", None))
EMOJIS = typer.Option(
    default=Setting.EMOJIS.default,  # type: ignore
    help="If true will instruct the LLMs to add applicable emojis",
)
COMMENTS = typer.Option(
    default=Setting.COMMENTS.default,  # type: ignore
    help="If true will generate the commit message commented out so that saving will abort the commit",
)
MODEL = typer.Option(
    default=Setting.MODEL.default,  # type: ignore
    help="The model to use (has to be available) according to the LiteLLM provider, as in ollama/llama2 or openai/gpt-5-mini",
)
API_KEY = typer.Option(
    default=Setting.API_KEY.default,  # type: ignore
    help="The api key to send to the model service (could use env based on the llm provider as in OPENAI_API_KEY)",
)
API_URL = typer.Option(
    default=Setting.API_KEY.default,  # type: ignore
    help="The api url if different than the model provider, as in ollama http://localhost:11434 by default",
)
DESCRIPTION_FILE = typer.Option(
    default=Setting.DESCRIPTION_FILE.default,  # type: ignore
    help="Description file of the purpose of the respository, usually a README.md file",
)
USE_TOOLS = typer.Option(
    default=Setting.USE_TOOLS.default,  # type: ignore
    help="Whether to allow tools usage or not while requesting llm responses",
)
MANUAL = typer.Option(
    default=Setting.MANUAL.default,  # type: ignore
    help="""
        If true will only generate the status message when explicitely called with called with the environment variable GIT_LLM_ON set on True, 
        you can set an alias such as `git config --global alias.llmc '!GIT_LLM_ON=True git commit'`
    """,
)
MANUAL_OVERRIDE = typer.Option(
    default=False,
    envvar="GIT_LLM_ON",
    hidden=True,
    help=""""
        When manual mode is acive, the 'GIT_LLM_ON' has to be set, this is used with the prepare message hook to prevent generating the llm comment on every commit
    """,
)
CONFIRM = typer.Option(
    None,
    "--confirm",
    help="Requests confirmation before changing a setting",
)
OUTPUT = typer.Option(hidden=True, parser=lambda s: sys.stdout, default=sys.stdout)
VERSION = typer.Option(
    None, "--version", callback=_get_version, help="shows current version"
)


@app.command(help="Reads respository description")
def get_description(
    folder: str = ".", description_file: str = DESCRIPTION_FILE
) -> Optional[str]:
    print(_get_description(file_path=Path(folder, description_file)))


@app.command(help="Generates a status message based on the git staged changes")
def status(
    with_emojis: bool = EMOJIS,
    model: str = MODEL,
    api_key: str | None = API_KEY,
    api_url: str | None = API_URL,
    description_file: str = DESCRIPTION_FILE,
    use_tools: bool = USE_TOOLS,
):
    generate(
        with_emojis=with_emojis,
        with_comments=False,
        model=model,
        api_key=api_key,
        api_url=api_url,
        description_file=description_file,
        use_tools=use_tools,
        manual=False,
    )


@app.command(
    help="Generates a commit message based on the git staged changes for the prepare-commit-msg hook"
)
def generate(
    with_emojis: bool = EMOJIS,
    with_comments: bool = COMMENTS,
    model: str = MODEL,
    api_key: str | None = API_KEY,
    api_url: str | None = API_URL,
    description_file: str | None = DESCRIPTION_FILE,
    use_tools: bool = USE_TOOLS,
    manual: bool = MANUAL,
    manual_override: bool = MANUAL_OVERRIDE,
    output: TextIO = OUTPUT,
):
    if manual and not manual_override:
        return

    folder = "."
    changes = get_staged_changes(folder=folder)
    if changes:
        commented = False
        file_path = description_file and Path(folder, description_file) or None
        client = LLMClient(
            model_name=model,
            use_emojis=with_emojis,
            api_key=api_key,
            api_url=api_url,
            use_tools=use_tools and file_path is not None and file_path.exists(),
            respository_description=lambda: _get_description(file_path),  # type: ignore
        )
        for message in client.message(changes, stream=False):
            if with_comments:
                if not commented:
                    print("# ", end="", file=output)
                    commented = True
                for c in message:
                    print(c, end="", file=output)
                    if c == "\n":
                        print("# ", end="", file=output)
            else:
                print(message, end="", file=output)
        print(file=output)
    else:
        print("No changes", file=output)


@app.command(help="Reads the configuration value")
def get_config(setting: Setting, scope: Scope = Scope.LOCAL):
    config = _get_config(setting.value)
    if config:
        print(config, end="")
    else:
        print(f"{setting.default} [default-value]")  # type: ignore


def _confirm(message: str, confirm: bool = CONFIRM):
    if confirm:
        confirmed = typer.confirm(message)
        if not confirmed:
            raise typer.Abort()


@app.command(
    help="Sets the configuration setting value, if no value is given resets the configuration to the default value"
)
def set_config(
    setting: Setting,
    value: str | None = None,
    scope: Scope = Scope.LOCAL,
    confirm: bool = CONFIRM,
):
    config = _get_config(setting.value)
    if value:
        if setting.flag:  # type: ignore
            value = _bool(value)  # type: ignore
        _confirm(
            f"Are you sure you want to update the setting: {setting.value} from {config} to {value}?",
            confirm=confirm,
        )
        _set_config(setting.value, value, scope=scope)  # type: ignore
        print(f"Updated {setting.value} to {_get_config(setting.value)}")
    else:
        if config:
            _confirm(
                f"Are you sure you want to remove the {setting.value} setting value: {config}?",
                confirm=confirm,
            )
            unset_config(setting.value, scope=scope)
            print(f"Restored {setting.value} to {setting.factory} [default-value]")  # type: ignore
        else:
            print(
                f"Setting {setting.value} is already using {setting.factory} [default-value]"  # type: ignore
            )


@app.callback()
def main(version: bool | None = VERSION):
    pass
