from enum import Enum
from git_llm_utils.utils import (
    _bool,
    get_tomlib_project,
    read_file,
    read_version,
    GIT_LLM_UTILS_DEBUG,
)
from git_llm_utils.git_commands import (
    get_config as _get_config,
    get_staged_changes,
    set_config as _set_config,
    unset_config,
    Scope,
)
from git_llm_utils.llm_cli import LLMClient
from pathlib import Path
from rich.console import Console
from rich.table import Table
from typing import Any, Callable, Optional, TextIO


import sys
import typer


class Setting(Enum):
    @staticmethod
    def __setting__(
        name: str,
        factory: Any | None = None,
        parser: Callable[[str], Any] | Any = None,
        help: str | None = None,
    ):
        default = _get_config(name, factory)
        if parser == _bool:
            help = f"{help} [default: {_bool(str(default)) and '--with-' or '--no-with-'}{name}]"
        option = typer.Option(  # type: ignore
            default=default,
            help=help,
            parser=parser,
            show_default=parser != _bool,
        )

        return (
            name,
            str(factory),
            option,
        )

    def __new__(
        cls,
        name: str,
        factory: Any,
        option: typer.Option,  # type: ignore
    ):
        enum = object.__new__(cls)
        enum._value_ = name
        enum.factory = factory  # type: ignore
        enum.option = option  # type: ignore
        return enum

    EMOJIS = __setting__(
        "emojis",
        factory=True,
        parser=_bool,
        help="If true will instruct the LLMs to add applicable emojis (see --config)",
    )
    COMMENTS = __setting__(
        "comments",
        factory=True,
        parser=_bool,
        help="If true will generate the commit message commented out so that saving it will exclude it from the commit message (see --config)",
    )
    MODEL = __setting__(
        "model",
        "ollama/qwen3-coder:480b-cloud",
        help="The model to use (has to be available) according to the LiteLLM provider, as in `ollama/llama2` or `openai/gpt-5-mini`",
    )
    API_KEY = __setting__(
        "api_key",
        help="The api key to send to the model service (could use env based on the llm provider as in OPENAI_API_KEY)",
    )
    API_URL = __setting__(
        "api_url",
        help="The api url if different than the model provider, as in ollama http://localhost:11434 by default",
    )
    DESCRIPTION_FILE = __setting__(
        "description-file",
        "README.md",
        help="Description file of the purpose of the respository, usually a README.md file",
    )
    TOOLS = __setting__(
        "tools",
        factory=False,
        parser=_bool,
        help="Whether to allow tools usage or not while requesting llm responses",
    )
    MANUAL = __setting__(
        "manual",
        factory=True,
        parser=_bool,
        help="""If true will only generate the commit status message when called with the GIT_LLM_ON environment variable set on True.
You can set an alias such as `git config --global alias.llmc '!GIT_LLM_ON=True git commit'`
If you want to generate a commit message for every commit, set `set-config manual --value False` (see --config)
        """,
    )


app = typer.Typer(
    help=get_tomlib_project().get("description", None), pretty_exceptions_enable=False
)
MANUAL_OVERRIDE = typer.Option(
    default=False,
    envvar="GIT_LLM_ON",
    hidden=True,
)
CONFIRM = typer.Option(
    None,
    "--confirm",
    help="Requests confirmation before changing a setting",
)
OUTPUT = typer.Option(hidden=True, parser=lambda s: sys.stdout, default=sys.stdout)
DEBUG = typer.Option(
    None,
    "--debug",
    help="enables debug information when it runs into a runtime failure",
    callback=lambda d: setattr(app, "pretty_exceptions_enable", d),
    envvar=GIT_LLM_UTILS_DEBUG,
    parser=_bool,
    hidden=True,
)


@app.command(help="Reads respository description")
def description(
    folder: str = ".",
    description_file: str = Setting.DESCRIPTION_FILE.option,  # type: ignore
    debug: bool = DEBUG,
) -> Optional[str]:
    print(read_file(file_path=Path(folder, description_file)))


@app.command(help="Generates a status message based on the git staged changes")
def status(
    with_emojis: bool = Setting.EMOJIS.option,  # type: ignore
    model: str = Setting.MODEL.option,  # type: ignore
    api_key: str | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None = Setting.API_URL.option,  # type: ignore
    description_file: str = Setting.DESCRIPTION_FILE.option,  # type: ignore
    tools: bool = Setting.TOOLS.option,  # type: ignore
    debug: bool = DEBUG,
):
    generate(
        with_emojis=with_emojis,
        with_comments=False,
        model=model,
        api_key=api_key,
        api_url=api_url,
        description_file=description_file,
        tools=tools,
        manual=False,
        output=sys.stdout,
        debug=debug,
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
    tools: bool = Setting.TOOLS.option,  # type: ignore
    manual: bool = Setting.MANUAL.option,  # type: ignore
    manual_override: bool = MANUAL_OVERRIDE,
    output: TextIO = OUTPUT,
    debug: bool = DEBUG,
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
            use_tools=tools and file_path is not None and file_path.exists(),
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
def get_config(
    setting: Setting,
    scope: Scope = Scope.LOCAL,
    debug: bool = DEBUG,
):
    config = _get_config(setting.value, scope=scope)
    if config:
        print(config)
    else:
        print(f"{setting.option.default} [default-value]")  # type: ignore


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
    debug: bool = DEBUG,
):
    config = _get_config(setting.value)
    if value:
        if setting.option.parser:  # type: ignore
            value = setting.option.parser(value)  # type: ignore
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
        table = Table("Setting", "Factory", "Default", "Description")
        for setting in Setting:
            table.add_row(
                setting.value,
                setting.factory,  # type: ignore
                str(setting.option.default),  # type: ignore
                setting.option.help,  # type: ignore
            )  # type: ignore
        console.print(table)
        raise typer.Exit()


@app.command(help="Installs the commit message hook (WIP)", hidden=True)
def install_hook(
    scope: Scope = Scope.LOCAL,
    confirm: bool = CONFIRM,
):
    program_name = sys.argv[0]
    _confirm(
        f"Are you sure you want to install the commit hook using {program_name}?",
        confirm=confirm,
    )
    ## REVIEW we can embedd the file with the dist or generate it in runtime
    ## the make file could also have a target to install the commit hook
    print(read_file(file_path=Path("prepare-commit-msg.sample")))
    typer.Abort()


@app.callback()
def _(
    version: bool | None = typer.Option(
        None, "--version", callback=_show_version, help="shows the current version"
    ),
    config: bool | None = typer.Option(
        None, "--config", callback=_show_config, help="shows the configuration options"
    ),
    debug: bool = DEBUG,
):
    pass


if __name__ == "__main__":
    app()
