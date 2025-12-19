from enum import Enum
from git_llm_utils.utils import (
    _bool,
    get_tomlib_project,
    read_version,
    read_file,
    write_file,
    execute_command,
    GIT_LLM_UTILS_DEBUG,
)
from git_llm_utils.git_commands import (
    get_config as _get_config,
    get_staged_changes,
    get_repository_path,
    set_config as _set_config,
    unset_config,
    Scope,
)
from git_llm_utils.llm_cli import LLMClient
from os import environ
from pathlib import Path
from rich.console import Console
from rich.table import Table
from typing import Any, Callable, Optional, TextIO


import sys
import typer

OVERRIDE = "GIT_LLM_ON"
ALIAS = f"!{OVERRIDE}=True git commit"
MESSAGE_HOOK = "prepare-commit-msg"
MESSAGE_HOOK_TEMPLATE = f"{MESSAGE_HOOK}.sample"


class Runtime:
    repository: Optional[Path] = None
    debug: bool = False
    confirm: bool = True

    @staticmethod
    def _set_repository(repository: str):
        Runtime.repository = get_repository_path(repository=repository)
        return Runtime.repository

    @staticmethod
    def _set_debug():
        setattr(app, "pretty_exceptions_enable", True)
        Runtime.debug = True
        return True

    @staticmethod
    def _set_confirm(confirm: bool):
        Runtime.confirm = confirm
        return True

    @staticmethod
    def _get_setting(
        name: str,
        factory: Any | None = None,
        parser: Callable[[str], Any] | Any = None,
        help: str | None = None,
        expose_value: bool = True,
    ):
        default = _get_config(
            name, default_value=factory, repository=Runtime.repository
        )
        if parser == _bool:
            help = f"{help} [default: {_bool(str(default)) and '--with-' or '--no-with-'}{name}]"

        return (
            name,
            str(factory),
            typer.Option(  # type: ignore
                default=default,
                help=help,
                parser=parser,
                expose_value=expose_value,
                show_default=parser != _bool,
            ),
        )


class Setting(Enum):
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

    EMOJIS = Runtime._get_setting(
        "emojis",
        factory=True,
        parser=_bool,
        help="If true will instruct the LLMs to add applicable emojis (see --config)",
    )
    COMMENTS = Runtime._get_setting(
        "comments",
        factory=True,
        parser=_bool,
        help="If true will generate the commit message commented out so that saving it will exclude it from the commit message (see --config)",
    )
    MODEL = Runtime._get_setting(
        "model",
        "ollama/qwen3-coder:480b-cloud",
        help="The model to use (has to be available) according to the LiteLLM provider, as in `ollama/llama2` or `openai/gpt-5-mini`",
    )
    MAX_INPUT_TOKENS = Runtime._get_setting(
        "max_input_tokens",
        help="How many tokens to send at most to the model",
        factory=262144,
        parser=int,
    )
    MAX_OUTPUT_TOKENS = Runtime._get_setting(
        "max_output_tokens",
        help="How many tokens to get at most from the model",
        factory=32768,
        parser=int,
    )
    API_KEY = Runtime._get_setting(
        "api_key",
        expose_value=False,
        help="The api key to send to the model service (could use env based on the llm provider as in OPENAI_API_KEY)",
    )
    API_URL = Runtime._get_setting(
        "api_url",
        help="The api url if different than the model provider, as in ollama http://localhost:11434 by default",
    )
    DESCRIPTION_FILE = Runtime._get_setting(
        "description-file",
        "README.md",
        help="Description file of the purpose of the respository, usually a README.md file",
    )
    TOOLS = Runtime._get_setting(
        "tools",
        factory=False,
        parser=_bool,
        help="Whether to allow tools usage or not while requesting llm responses",
    )
    MANUAL = Runtime._get_setting(
        "manual",
        factory=True,
        parser=_bool,
        help=f"""If true will only generate the commit status message when called with the {OVERRIDE} environment variable set on True.
You can set an alias such as `git config --global alias.llmc '{ALIAS}'`
If you want to generate a commit message for every commit, set `set-config manual --value False` (see --config)
        """,
    )


app = typer.Typer(
    help=get_tomlib_project().get("description", None), pretty_exceptions_enable=False
)


@app.command(help="Reads the respository description")
def description(
    description_file: str = Setting.DESCRIPTION_FILE.option,  # type: ignore
) -> Optional[str]:
    print(
        read_file(
            file_path=Path(Runtime.repository or ".", description_file),
            debug=Runtime.debug,
        )
    )


@app.command(help="Generates a status message based on the git staged changes")
def status(
    with_emojis: bool = Setting.EMOJIS.option,  # type: ignore
    model: str = Setting.MODEL.option,  # type: ignore
    max_input_tokens: int = Setting.MAX_INPUT_TOKENS.option,  # type: ignore
    max_output_tokens: int = Setting.MAX_OUTPUT_TOKENS.option,  # type: ignore
    api_key: str | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None = Setting.API_URL.option,  # type: ignore
    description_file: str = Setting.DESCRIPTION_FILE.option,  # type: ignore
    tools: bool = Setting.TOOLS.option,  # type: ignore
):
    generate(
        with_emojis=with_emojis,
        with_comments=False,
        model=model,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        api_key=api_key,
        api_url=api_url,
        description_file=description_file,
        tools=tools,
        manual=False,
        output=sys.stdout,
    )


@app.command(
    help=f"Generates a commit message based on the git staged changes for the {MESSAGE_HOOK} hook"
)
def generate(
    with_emojis: bool = Setting.EMOJIS.option,  # type: ignore
    with_comments: bool = Setting.COMMENTS.option,  # type: ignore
    model: str = Setting.MODEL.option,  # type: ignore
    max_input_tokens: int = Setting.MAX_INPUT_TOKENS.option,  # type: ignore
    max_output_tokens: int = Setting.MAX_OUTPUT_TOKENS.option,  # type: ignore
    api_key: str | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None = Setting.API_URL.option,  # type: ignore
    description_file: str | None = Setting.DESCRIPTION_FILE.option,  # type: ignore
    tools: bool = Setting.TOOLS.option,  # type: ignore
    manual: bool = Setting.MANUAL.option,  # type: ignore
    manual_override: bool = typer.Option(
        None,
        "--override",
        envvar="GIT_LLM_ON",
        hidden=True,
    ),
    output: TextIO = typer.Option(
        hidden=True, parser=lambda _: sys.stdout, default=sys.stdout
    ),
):
    if manual and not manual_override:
        return

    changes = get_staged_changes(repository=Runtime.repository)
    if changes:
        commented = False
        file_path = (
            description_file
            and Path(Runtime.repository or ".", description_file)
            or None
        )
        client = LLMClient(
            use_emojis=with_emojis,
            model_name=model,
            max_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
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
):
    config = _get_config(
        setting.value,
        repository=Runtime.repository,
        scope=scope,
    )
    if config:
        print(config)
    else:
        print(f"{setting.option.default} [default-value]")  # type: ignore


def _confirm(message: str):
    if Runtime.confirm:
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
):
    config = _get_config(setting.value, repository=Runtime.repository)
    if value:
        if setting.option.parser:  # type: ignore
            value = setting.option.parser(value)  # type: ignore
        _confirm(
            f"Are you sure you want to update the setting: {setting.value} from {config} to {value}?",
        )
        _set_config(setting.value, value, scope=scope, repository=Runtime.repository)  # type: ignore
        print(
            f"Updated {setting.value} to {_get_config(setting.value, repository=Runtime.repository)}"
        )
    else:
        if config:
            _confirm(
                f"Are you sure you want to remove the {setting.value} setting value: {config}?",
            )
            unset_config(setting.value, scope=scope, repository=Runtime.repository)
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


@app.command(help="Installs the commit alias to trigger message hook", hidden=True)
def install_alias(
    scope: Scope = Scope.LOCAL,
    command: str = typer.Option(help="The name of the command alias", default="llmc"),
):
    _confirm(f"Do you want to install the git comamnd alias: {command}")
    _set_config(
        f"{command}",
        namespace="alias",
        scope=scope,
        value=ALIAS,
        repository=Runtime.repository,
        abort_on_error=Runtime.debug,
    )


@app.command(
    help="Installs the commit message hook, only works with the venv source code or the binary distribution",
)
def install_hook(
    overwrite: bool = typer.Option(
        None,
        "--overwrite",
        help="Overwrite the commit message hook if it already exists",
    ),
):
    is_venv = sys.prefix != sys.base_prefix
    if is_venv:
        directory = Path(environ.get("VIRTUAL_ENV", sys.argv[0])).parent
        program_name = f"uv --directory {directory} run git-llm-utils"
    else:
        program_name = sys.executable

    cmd = program_name.split()
    cmd.append("--version")
    version = execute_command(cmd)
    if not version or read_version() not in version:
        print(
            "git-llm-utils version not detected, please run this command with the git-llm-utils client",
            file=sys.stderr,
        )
        typer.Exit(-2)

    if not program_name:
        print(
            "git-llm-utils not detected, please run this command with the git-llm-utils client",
            file=sys.stderr,
        )
        typer.Exit(-3)

    if not Runtime.repository:
        if not Runtime._set_repository("."):
            print("No git repository detected in the current folder", file=sys.stderr)
            typer.Exit(-4)

    hook_template_path = (Path.cwd() / __file__).with_name(MESSAGE_HOOK_TEMPLATE)
    _confirm(
        f"Are you sure you want to install the commit message hook in the '{Runtime.repository}' repository, using '{program_name}' command? ({hook_template_path})",
    )

    hook = read_file(
        hook_template_path,
        debug=Runtime.debug,
    )
    if hook:
        hook = hook.replace(
            "path/to/git-llm-utils",
            program_name,
        )
        hook_path = f"{Runtime.repository}/.git/hooks/{MESSAGE_HOOK}"
        if write_file(Path(hook_path), hook, overwrite=overwrite):
            execute_command(["chmod", "+x", hook_path])
        else:
            print(
                f"Failed to write {MESSAGE_HOOK} to {hook_path}, use --overwrite if the hook is already installed",
                file=sys.stderr,
            )
            typer.Exit(-5)
    else:
        print(
            f"Failed to read {MESSAGE_HOOK_TEMPLATE} from {hook_template_path}",
            file=sys.stderr,
        )
        typer.Exit(-6)


@app.callback()
def _(
    version: bool | None = typer.Option(
        None, "--version", callback=_show_version, help="shows the current version"
    ),
    config: bool | None = typer.Option(
        None,
        "--config",
        callback=_show_config,
        help="shows the all configuration options",
    ),
    repository: Path = typer.Option(
        help="Git Repository path, if not given will assume the current path is the repository",
        parser=Runtime._set_repository,
        default=None,
        allow_from_autoenv=True,
        envvar="GIT_LLM_UTILS_REPO",
    ),
    confirm: bool = typer.Option(
        callback=Runtime._set_confirm,
        help="Requests confirmation before changing a setting",
        default=Runtime.confirm,
    ),
    debug: bool = typer.Option(
        None,
        "--debug",
        help="enables debug information when it runs into a runtime failure",
        callback=Runtime._set_debug,
        envvar=GIT_LLM_UTILS_DEBUG,
        hidden=True,
    ),
):
    pass


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        app()
    else:
        print(
            "Please run the app using the git-llm-utils command",
            file=sys.stderr,
        )
        sys.exit(-1)
