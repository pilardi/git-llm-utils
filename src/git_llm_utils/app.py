from enum import Enum
from io import StringIO
from git_llm_utils.utils import (
    _bool,
    get_tomlib_project,
    read_version,
    read_file,
    write_file,
    execute_command,
    execute_raw_command,
    ErrorHandler,
)
from git_llm_utils.git import (
    get_config as _get_config,
    get_staged_changes,
    get_repository_path,
    set_config as _set_config,
    unset_config,
    Scope,
)
from git_llm_utils.llm import LLMClient
from os import environ
from pathlib import Path
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table
from typing import Any, Callable, Optional, TextIO, Tuple


import sys
import typer

OVERRIDE = "GIT_LLM_ON"
COMMIT_ALIAS = "llmc"
COMMIT_ALIAS_GIT_COMMAND = f"!{OVERRIDE}=True git commit"
COMMIT_COMMAND = ["git", "commit", "-F", "-"]
MESSAGE_HOOK = "prepare-commit-msg"
MESSAGE_HOOK_TEMPLATE = f"{MESSAGE_HOOK}.sample"
NO_CHANGES_MESSAGE = 'no changes added to commit (use "git add" and/or "git commit -a")'


class SettingLoader(BaseModel):
    name: str
    key: str
    factory: Any | None  # the code value
    config: Any | None  # the current config value
    value: Any | None  # the cli value
    hint: str | None
    bool_hint: str | None = "with-"
    parser: Callable[[str], Any] | Any = None

    def load_config(self, scope: Optional[Scope] = None) -> Tuple[Any, str]:
        self.config = _get_config(
            self.key,
            default_value=self.factory,
            repository=Runtime.repository,
            scope=scope,
        )
        if self.config is not None and self.parser:
            self.config = self.parser(self.config)
        if self.parser == _bool:
            help = f"{self.hint} [bold green]\\[default: {_bool(str(self.config)) and f'--{self.bool_hint}' or f'--no-{self.bool_hint}'}{self.name}][/bold green]"
        else:
            help = (
                f"{self.hint} [bold green]\\[default: {str(self.config)}][/bold green]"
            )
        return (self.config, help)

    def set_value(self, value: Any):
        if self.parser is None or value is None:
            self.value = value
        else:
            self.value = self.parser(value)

    def get_value(self, given: Any) -> Any | None:
        if given is not None:
            return given
        if self.value is not None:
            return self.value
        if self.config is not None:
            return self.config
        return self.factory


class Runtime:
    repository: Optional[Path] = get_repository_path(abort_on_error=False)
    confirm: bool = True
    settings: dict[str, Tuple[SettingLoader, typer.models.OptionInfo]] = {}

    @staticmethod
    def _set_repository(repository: str):
        previous = Runtime.repository
        Runtime.repository = get_repository_path(repository=repository)
        if previous != Runtime.repository:
            for loader, option in Runtime.settings.values():
                (option.default, option.help) = loader.load_config()
        return Runtime.repository

    @staticmethod
    def _set_debug(debug: bool = False):
        ErrorHandler.debug = debug
        setattr(app, "pretty_exceptions_enable", ErrorHandler.debug)
        return ErrorHandler.debug

    @staticmethod
    def _set_confirm(confirm: bool = False):
        Runtime.confirm = confirm
        return Runtime.confirm

    @staticmethod
    def load_setting(
        name: str,
        factory: Any | None = None,
        parser: Callable[[str], Any] | Any = None,
        hint: str | None = None,
        bool_hint: str | None = "with-",
        envvar: Optional[str] = None,
    ) -> Tuple[SettingLoader, typer.models.OptionInfo]:
        loader = SettingLoader(
            name=name,
            key=name.strip().replace("_", "-"),
            factory=factory,
            config=None,
            value=None,
            hint=hint,
            bool_hint=bool_hint,
            parser=parser,
        )
        (_, help) = loader.load_config()
        option = typer.Option(  # type: ignore
            default=None,
            help=help,
            parser=parser,
            envvar=envvar,
            expose_value=False,
            show_default=parser != _bool,
            callback=lambda v: loader.set_value(v),
        )
        Runtime.settings[name] = (loader, option)
        return Runtime.settings[name]

    @staticmethod
    def get_config(setting: str, scope: Optional[Scope] = None) -> Optional[Any]:
        if setting in Runtime.settings:
            return Runtime.settings[setting][0].load_config(scope=scope)[0]
        return None

    @staticmethod
    def set_config(
        setting: str, scope: Scope, value: Optional[str] = None
    ) -> Optional[Any]:
        s = Runtime.settings[setting][0]
        if value is not None:
            _set_config(s.key, value, scope=scope, repository=Runtime.repository)
        else:
            unset_config(s.key, scope=scope, repository=Runtime.repository)

    @staticmethod
    def get_value(setting: str, given: Any = None) -> Optional[Any]:
        if setting in Runtime.settings:
            return Runtime.settings[setting][0].get_value(given)
        return None


class Setting(Enum):
    def __new__(cls, loader: SettingLoader, option: typer.models.OptionInfo):
        enum = object.__new__(cls)
        enum._value_ = loader.name
        enum.factory = loader.factory  # type: ignore
        enum.option = option  # type: ignore
        return enum

    EMOJIS = Runtime.load_setting(
        "emojis",
        factory=True,
        parser=_bool,
        hint="If true will instruct the LLMs to add applicable emojis (see --config)",
    )
    COMMENTS = Runtime.load_setting(
        "comments",
        factory=True,
        parser=_bool,
        hint="If true will generate the commit message commented out so that saving it will exclude it from the commit message (see --config)",
    )
    MODEL = Runtime.load_setting(
        "model",
        factory="ollama/qwen3-coder:480b-cloud",
        hint="The model to use (has to be available) according to the LiteLLM provider, as in `ollama/llama2` or `openai/gpt-5-mini`",
    )
    MAX_INPUT_TOKENS = Runtime.load_setting(
        "max_input_tokens",
        factory=262144,
        parser=int,
        hint="How many tokens to send at most to the model",
    )
    MAX_OUTPUT_TOKENS = Runtime.load_setting(
        "max_output_tokens",
        factory=32768,
        parser=int,
        hint="How many tokens to get at most from the model",
    )
    API_KEY = Runtime.load_setting(
        "api_key",
        envvar="GIT_LLM_API_KEY",
        hint="The api key to send to the model service (could use env based on the llm provider as in OPENAI_API_KEY)",
    )
    API_URL = Runtime.load_setting(
        "api_url",
        hint="The api url if different for every  model provider, as in ollama it is http://localhost:11434 by default",
    )
    DESCRIPTION_FILE = Runtime.load_setting(
        "description-file",
        factory="README.md",
        hint="Description file of the purpose of the respository, usually a README.md file",
    )
    TOOLS = Runtime.load_setting(
        "tools",
        factory=False,
        parser=_bool,
        hint="Whether to allow tools usage or not while requesting llm responses",
    )
    MANUAL = Runtime.load_setting(
        "manual",
        factory=True,
        parser=_bool,
        bool_hint="",
        hint=f"""If true will only generate the commit status message when called with the {OVERRIDE} environment variable set on True.
You can set an alias such as `git config --global alias.llmc '{COMMIT_ALIAS_GIT_COMMAND}'`
If you want to generate a commit message for every commit, set `set-config manual --value False` (see --config)
        """,
    )


app = typer.Typer(
    help=get_tomlib_project().get("description", None),
    pretty_exceptions_enable=False,
    rich_markup_mode="rich",
)


@app.command(help="Reads the respository description")
def description(
    description_file: str = Setting.DESCRIPTION_FILE.option,  # type: ignore
) -> Optional[str]:
    print(read_file(file_path=Path(Runtime.repository or ".", description_file)))


@app.command(
    help=f"Passes the status output as input to the given command arguments, as in `git-llm-utils command -- {' '.join(COMMIT_COMMAND)}`"
)
def command(
    args: list[str],
    with_emojis: bool | None = Setting.EMOJIS.option,  # type: ignore
    model: str | None = Setting.MODEL.option,  # type: ignore
    max_input_tokens: int | None = Setting.MAX_INPUT_TOKENS.option,  # type: ignore
    max_output_tokens: int | None = Setting.MAX_OUTPUT_TOKENS.option,  # type: ignore
    api_key: str | None | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None | None = Setting.API_URL.option,  # type: ignore
    description_file: str | None = Setting.DESCRIPTION_FILE.option,  # type: ignore
    tools: bool | None = Setting.TOOLS.option,  # type: ignore
):
    output = StringIO()
    generated = generate(
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
        output=output,
    )
    value = output.getvalue()
    if generated:
        _confirm(f"\n{value}\n{' '.join(args)}")
        execute_raw_command(args, input=value)
    else:
        print(value)


@app.command(
    help=f"commit the current change set using the status message using `{' '.join(COMMIT_COMMAND)}`"
)
def commit(
    with_emojis: bool | None = Setting.EMOJIS.option,  # type: ignore
    model: str | None = Setting.MODEL.option,  # type: ignore
    max_input_tokens: int | None = Setting.MAX_INPUT_TOKENS.option,  # type: ignore
    max_output_tokens: int | None = Setting.MAX_OUTPUT_TOKENS.option,  # type: ignore
    api_key: str | None | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None | None = Setting.API_URL.option,  # type: ignore
    description_file: str | None = Setting.DESCRIPTION_FILE.option,  # type: ignore
    tools: bool | None = Setting.TOOLS.option,  # type: ignore
):
    command(
        COMMIT_COMMAND,
        with_emojis,
        model,
        max_input_tokens,
        max_output_tokens,
        api_key,
        api_url,
        description_file,
        tools,
    )


@app.command(help="Generates a status message based on the git staged changes")
def status(
    with_emojis: bool | None = Setting.EMOJIS.option,  # type: ignore
    model: str | None = Setting.MODEL.option,  # type: ignore
    max_input_tokens: int | None = Setting.MAX_INPUT_TOKENS.option,  # type: ignore
    max_output_tokens: int | None = Setting.MAX_OUTPUT_TOKENS.option,  # type: ignore
    api_key: str | None | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None | None = Setting.API_URL.option,  # type: ignore
    description_file: str | None = Setting.DESCRIPTION_FILE.option,  # type: ignore
    tools: bool | None = Setting.TOOLS.option,  # type: ignore
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
    with_emojis: bool | None = Setting.EMOJIS.option,  # type: ignore
    with_comments: bool | None = Setting.COMMENTS.option,  # type: ignore
    model: str | None = Setting.MODEL.option,  # type: ignore
    max_input_tokens: int | None = Setting.MAX_INPUT_TOKENS.option,  # type: ignore
    max_output_tokens: int | None = Setting.MAX_OUTPUT_TOKENS.option,  # type: ignore
    api_key: str | None = Setting.API_KEY.option,  # type: ignore
    api_url: str | None = Setting.API_URL.option,  # type: ignore
    description_file: str | None = Setting.DESCRIPTION_FILE.option,  # type: ignore
    tools: bool | None = Setting.TOOLS.option,  # type: ignore
    manual: bool | None = Setting.MANUAL.option,  # type: ignore
    manual_override: bool = typer.Option(
        None,
        "--override",
        envvar=OVERRIDE,
        hidden=True,
    ),
    output: TextIO = typer.Option(
        hidden=True, parser=lambda _: sys.stdout, default=sys.stdout
    ),
) -> bool:
    if Runtime.get_value(Setting.MANUAL.value, manual) and not manual_override:
        ErrorHandler.report_debug(f"requested manual {manual} but override was not set")
        return False

    changes = get_staged_changes(repository=Runtime.repository)
    if changes is None or not changes.strip():
        print(NO_CHANGES_MESSAGE, file=output)
        return False

    file_path = (
        description_file and Path(Runtime.repository or ".", description_file) or None
    )
    client = LLMClient(
        use_emojis=Runtime.get_value(Setting.EMOJIS.value, with_emojis),  # type: ignore
        model_name=Runtime.get_value(Setting.MODEL.value, model),  # type: ignore
        max_tokens=Runtime.get_value(Setting.MAX_INPUT_TOKENS.value, max_input_tokens),  # type: ignore
        max_output_tokens=Runtime.get_value(
            Setting.MAX_OUTPUT_TOKENS.value, max_output_tokens
        ),  # type: ignore
        api_key=Runtime.get_value(Setting.API_KEY.value, api_key),
        api_url=Runtime.get_value(Setting.API_URL.value, api_url),
        use_tools=Runtime.get_value(Setting.TOOLS.value, tools)
        and file_path is not None
        and file_path.exists(),  # type: ignore
        respository_description=lambda: read_file(file_path),  # type: ignore
    )
    comments = Runtime.get_value(Setting.COMMENTS.value, with_comments)

    commented = False
    for message in client.message(changes, stream=False):
        if comments:
            for c in message:
                if not commented:
                    print("# ", end="", file=output)
                    commented = True
                print(c, end="", file=output)
                if c == "\n":
                    commented = False
        else:
            print(message, end="", file=output)
    return True


@app.command(help="Reads the configuration value")
def get_config(
    setting: Setting,
    scope: Scope = Scope.LOCAL,
):
    config = Runtime.get_config(setting=setting.value, scope=scope)
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
    if scope == Scope.LOCAL and Runtime.repository is None:
        ErrorHandler.report_error(
            f"no git repository detected, use scope {Scope.SYSTEM.name} or {Scope.GLOBAL.name} to change {setting.name} settings or use the --repository option to specify the local scope",
            show=True,
        )
        raise typer.Exit(ErrorHandler.INVALID_SCOPE)

    config = Runtime.get_config(setting=setting.value, scope=scope)
    if value:
        if setting.option.parser:  # type: ignore
            value = setting.option.parser(value)  # type: ignore
        _confirm(
            f"Are you sure you want to update the setting: {setting.value} from {config} to {value}?",
        )
        Runtime.set_config(setting.value, scope=scope, value=value)  # type: ignore
        print(
            f"Updated {setting.value} to {Runtime.get_config(setting=setting.value, scope=scope)}"
        )
    else:
        if config:
            _confirm(
                f"Are you sure you want to remove the {setting.value} setting value: {config}?",
            )
            (Runtime.set_config(setting.value, scope=scope),)  # type: ignore
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
                str(setting.factory),  # type: ignore
                str(Runtime.get_value(setting=setting.value)),  # type: ignore
                setting.option.help,  # type: ignore
            )  # type: ignore
        console.print(table)
        raise typer.Exit()


COMMIT_ALIAS_COMMAND = typer.Option(
    help="The name of the commit alias", default=COMMIT_ALIAS
)
STATUS_ALIAS_COMMAND = typer.Option(
    help="The name of the status alias", default=COMMIT_ALIAS
)
OVERWRITE = typer.Option(
    None,
    "--overwrite",
    help="Overwrite the commit message hook if it already exists",
)


@app.command(
    help=f"Installs the commit alias to trigger message hook, as in `git {COMMIT_ALIAS}`"
)
def install_alias(
    scope: Scope = Scope.LOCAL,
    command: str = COMMIT_ALIAS_COMMAND,
):
    _confirm(f"Do you want to install the git comamnd alias: `git {command}`")
    _set_config(
        f"{command}",
        namespace="alias",
        scope=scope,
        value=COMMIT_ALIAS_GIT_COMMAND,
        repository=Runtime.repository,
        abort_on_error=ErrorHandler.debug,
    )


@app.command(
    help="Installs the commit message hook, only works with the venv source code or the binary distribution",
)
def install_hook(overwrite: bool = OVERWRITE):
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
        ErrorHandler.report_error(
            "git-llm-utils version not detected, please run this command with the git-llm-utils client",
            show=True,
        )
        raise typer.Exit(ErrorHandler.INVALID_CLIENT)

    if not program_name:
        ErrorHandler.report_error(
            "git-llm-utils not detected, please run this command with the git-llm-utils client",
            show=True,
        )
        raise typer.Exit(ErrorHandler.CLIENT_NOT_DETECTED)

    if not Runtime.repository:
        if not Runtime._set_repository("."):
            ErrorHandler.report_error(
                "No git repository detected in the current folder", show=True
            )
            raise typer.Exit(ErrorHandler.NO_GIT_REPOSITORY)

    hook_template_path = (Path.cwd() / __file__).with_name(MESSAGE_HOOK_TEMPLATE)
    _confirm(
        f"Are you sure you want to install the commit message hook in the '{Runtime.repository}' repository, using '{program_name}' command?",
    )

    hook = read_file(hook_template_path)
    if hook:
        hook = hook.replace(
            "path/to/git-llm-utils",
            program_name,
        )
        hook_path = f"{Runtime.repository}/.git/hooks/{MESSAGE_HOOK}"
        if write_file(Path(hook_path), hook, overwrite=overwrite):
            execute_command(["chmod", "+x", hook_path])
        else:
            ErrorHandler.report_error(
                f"Failed to write {MESSAGE_HOOK} to {hook_path}, use --overwrite if the hook is already installed",
                show=True,
            )
            raise typer.Exit(ErrorHandler.FILE_ALREADY_EXISTS)
    else:
        ErrorHandler.report_error(
            f"Failed to read {MESSAGE_HOOK_TEMPLATE} from {hook_template_path}",
            show=True,
        )
        raise typer.Exit(ErrorHandler.INVALID_HOOK_TEMPLATE)


@app.command(
    help=f"Installs the commit message hook and alias in the current repository, as in `git {COMMIT_ALIAS}`",
)
def install(
    command: str = COMMIT_ALIAS_COMMAND,
    overwrite: bool = OVERWRITE,
):
    install_hook(overwrite=overwrite)
    install_alias(
        scope=Scope.LOCAL, command=command
    )  # the hook is only local to the repo


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
        envvar="GIT_LLM_REPO",
    ),
    confirm: bool = typer.Option(
        help="Requests confirmation before changing a setting",
        callback=Runtime._set_confirm,
        default=Runtime.confirm,
        parser=_bool,
        envvar="GIT_LLM_CONFIRM",
    ),
    debug: bool = typer.Option(
        None,
        "--debug",
        help="enables debug information when it runs into a runtime failure",
        callback=Runtime._set_debug,
        parser=_bool,
        envvar=ErrorHandler.GIT_LLM_DEBUG,
        hidden=True,
    ),
):
    pass


def safe_run():
    try:
        app()
    except Exception as e:
        ErrorHandler.report_error(f"Application failed: {e}", show=True)
        if ErrorHandler.debug:
            raise e
        typer.Exit(ErrorHandler.UNDEFINED_ERROR)
