from enum import Enum
from git_llm_utils.utils import _bool, get_tomlib_project, read_file, read_version
from git_llm_utils.git_commands import (
    get_config as _get_config,
    get_default_setting as _get_default_setting,
    get_staged_changes,
    set_config as _set_config,
    unset_config,
    Scope,
)
from git_llm_utils.llm_cli import LLMClient
from pathlib import Path
from rich.console import Console
from rich.table import Table
from typing import Any, Optional, TextIO


import sys
import typer


class Setting(Enum):
    def __new__(
        cls,
        value,
        flag: bool,
        default: Any | None,
        factory: Any | None,
        help: str | None,
    ):
        enum = object.__new__(cls)
        enum._value_ = value
        enum.flag = flag  # type: ignore
        enum.default = default  # type: ignore
        enum.factory = factory  # type: ignore
        enum.help = help  # type: ignore
        enum.option = typer.Option(  # type: ignore
            default=default,
            help=help,
        )
        return enum

    EMOJIS = _get_default_setting(
        "emojis",
        "True",
        flag=True,
        help="If true will instruct the LLMs to add applicable emojis",
    )
    COMMENTS = _get_default_setting(
        "comments",
        "True",
        flag=True,
        help="If true will generate the commit message commented out so that saving will abort the commit",
    )
    MODEL = _get_default_setting(
        "model",
        "ollama/qwen3-coder:480b-cloud",
        help="The model to use (has to be available) according to the LiteLLM provider, as in ollama/llama2 or openai/gpt-5-mini",
    )
    API_KEY = _get_default_setting(
        "api_key",
        None,
        help="The api key to send to the model service (could use env based on the llm provider as in OPENAI_API_KEY)",
    )
    API_URL = _get_default_setting(
        "api_url",
        None,
        help="The api url if different than the model provider, as in ollama http://localhost:11434 by default",
    )
    DESCRIPTION_FILE = _get_default_setting(
        "description_file",
        "README.md",
        help="Description file of the purpose of the respository, usually a README.md file",
    )
    USE_TOOLS = _get_default_setting(
        "tools",
        "False",
        flag=True,
        help="Whether to allow tools usage or not while requesting llm responses",
    )
    MANUAL = _get_default_setting(
        "manual",
        "True",
        flag=True,
        help="""If true will only generate the status message when explicitely called with called with the environment variable GIT_LLM_ON set on True, 
        you can set an alias such as `git config --global alias.llmc '!GIT_LLM_ON=True git commit'`""",
    )


app = typer.Typer(help=get_tomlib_project().get("description", None))
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
VERBOSE = typer.Option(None, "--verbose", envvar="verbose", parser=_bool, hidden=True)


@app.command(help="Reads respository description")
def get_description(
    folder: str = ".",
    description_file: str = Setting.DESCRIPTION_FILE.option,  # type: ignore
) -> Optional[str]:
    print(read_file(file_path=Path(folder, description_file)))


@app.command(help="Generates a status message based on the git staged changes")
def status(
    with_emojis: bool = Setting.EMOJIS.option,  # type: ignore
    model: str = Setting.MODEL.option,  # type: ignore
    api_key: str | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None = Setting.API_URL.option,  # type: ignore
    description_file: str = Setting.DESCRIPTION_FILE.option,  # type: ignore
    use_tools: bool = Setting.USE_TOOLS.option,  # type: ignore
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
        output=sys.stdout,
    )


@app.command(
    help="Generates a commit message based on the git staged changes for the prepare-commit-msg hook"
)
def generate(
    with_emojis: bool = Setting.EMOJIS.option,  # type: ignore
    with_comments: bool = Setting.COMMENTS.option,  # type: ignore
    model: str = Setting.MODEL.option,  # type: ignore
    api_key: str | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None = Setting.API_URL.option,  # type: ignore
    description_file: str | None = Setting.DESCRIPTION_FILE.option,  # type: ignore
    use_tools: bool = Setting.USE_TOOLS.option,  # type: ignore
    manual: bool = Setting.MANUAL.option,  # type: ignore
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
            respository_description=lambda: read_file(file_path),  # type: ignore
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
        print(config)
    else:
        print(f"{setting.default} [default-value]")  # type: ignore


def _confirm(message: str, confirm: bool = CONFIRM):
    if confirm:
        confirmed = typer.confirm(message)
        if not confirmed:
            raise typer.Abort()


@app.command(
    help="Sets the configuration value, if no value is given resets the configuration to the default value"
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


def _show_version(show: bool):
    if show:
        print(f"Version is {read_version()}")
        raise typer.Exit()


def _show_config(show: bool):
    if show:
        console = Console()
        table = Table("Setting", "Default", "Value", "Description")
        for setting in Setting:
            table.add_row(setting.value, setting.factory, setting.default, setting.help)  # type: ignore
        console.print(table)
        raise typer.Exit()


@app.callback()
def _(
    version: bool | None = typer.Option(
        None, "--version", callback=_show_version, help="shows the current version"
    ),
    config: bool | None = typer.Option(
        None, "--config", callback=_show_config, help="shows the configuration"
    ),
):
    pass


if __name__ == "__main__":
    app()
