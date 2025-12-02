from enum import Enum
from io import StringIO
from git_commands import get_config as _get_config, get_staged_changes, set_config as _set_config, unset_config, Scope
from llm_cli import LLMClient
from pathlib import Path
from typing import Optional, TextIO
from typing_extensions import Annotated

import sys
import typer
import os

README = 'README.md'
def _bool(value : str) -> bool:
    return value and value.lower() in ('1', 'true', 'yes') or False

GIT_LLM_ON=_bool(os.environ.get('GIT_LLM_ON', 'False'))

class Setting(Enum):
    EMOJIS  = "emojis"
    COMMENTS = "comments"
    MODEL   = "model"
    API_KEY = "api_key"
    API_URL = "api_url"
    DESCRIPTION_FILE = "description_file"
    USE_TOOLS = "use_tools"
    MANUAL = "manual"

DEFAULT_SETTINGS = {
    Setting.EMOJIS: _get_config(Setting.EMOJIS.value, 'True'),
    Setting.COMMENTS: _get_config(Setting.COMMENTS.value, 'True'),
    Setting.MODEL: _get_config(Setting.MODEL.value, 'ollama/qwen3-coder:480b-cloud'),
    Setting.API_KEY: _get_config(Setting.API_KEY.value, None),
    Setting.API_URL: _get_config(Setting.API_KEY.value, None),
    Setting.DESCRIPTION_FILE: _get_config(Setting.DESCRIPTION_FILE.value, README),
    Setting.USE_TOOLS: _get_config(Setting.USE_TOOLS.value, 'False'),
    Setting.MANUAL: _get_config(Setting.MANUAL.value, 'True')
}

app = typer.Typer()
EMOJIS = typer.Option(
    default=_bool(DEFAULT_SETTINGS[Setting.EMOJIS]), # type: ignore
    help="If true will instruct the LLMs to add applicable emojis"
)
COMMENTS = typer.Option(
    default=_bool(DEFAULT_SETTINGS[Setting.COMMENTS]), # type: ignore
    help="If true will generate the commit message commented out so that saving will abort the commit"
)
MODEL = typer.Option(
    default=DEFAULT_SETTINGS[Setting.MODEL],
    help="The model to use (has to be available) according to the LiteLLM provider, as in ollama/llama2 or openai/gpt-5-mini"
)
API_KEY = typer.Option(
    default=DEFAULT_SETTINGS[Setting.API_KEY],
    help="The api key to send to the model service (could use env based on the llm provider as in OPENAI_API_KEY)"
)
API_URL = typer.Option(
    default=DEFAULT_SETTINGS[Setting.API_KEY],
    help="The api url if different than the model provider, as in ollama http://localhost:11434 by default"
)
DESCRIPTION_FILE = typer.Option(
    default=DEFAULT_SETTINGS[Setting.DESCRIPTION_FILE],
    help="Description file of the purpose of the respository, usually a README.md file"
)
USE_TOOLS= typer.Option(
    default=_bool(DEFAULT_SETTINGS[Setting.USE_TOOLS]), # type: ignore
    help="Whether to allow tools usage or not while requesting llm responses"
)
MANUAL= typer.Option(
    default=_bool(DEFAULT_SETTINGS[Setting.MANUAL]), # type: ignore
    help="""
        If true will only generate the status message when explicitely called with called with the environment variable GIT_LLM_ON set on True, 
        you can set an alias such as `git config --global alias.llmc '!GIT_LLM_ON=True git commit'`
    """
)

def _get_description(file_path : Path | None) -> Optional[str]:
    if file_path is not None and file_path.exists():
        with open(file_path, 'r') as file:
            return file.read()
    else:
        print(f"Description file {file_path} does not exist", file=sys.stderr)
    return None

@app.command(help="Reads respository description")
def get_description(folder : str = '.', description_file : str = DESCRIPTION_FILE) -> Optional[str]:
    print(_get_description(file_path = Path(folder, description_file)))

@app.command(help="Generates a status message based on the git staged changes")
def status(
        with_emojis : bool = EMOJIS,
        model : str = MODEL,
        api_key : str | None = API_KEY,
        api_url : str | None = API_URL,
        description_file : str = DESCRIPTION_FILE,
        use_tools: bool = USE_TOOLS
    ):
    generate(
        with_emojis=with_emojis,
        with_comments=False,
        model=model,
        api_key=api_key,
        api_url=api_url,
        description_file=description_file,
        use_tools=use_tools,
        manual=False
    )

def _get_output(value: str):
    """
    This is a hack to let a command accept a TextIO for testing purposes (however this is not supported in the cli, hence the hidden flag)
    """
    return sys.stdout

@app.command(help="Generates a commit message based on the git staged changes for the prepare-commit-msg hook")
def generate(
        with_emojis : bool = EMOJIS,
        with_comments : bool = COMMENTS,
        model : str = MODEL,
        api_key : str | None = API_KEY,
        api_url : str | None = API_URL,
        description_file : str | None = DESCRIPTION_FILE,
        use_tools: bool = USE_TOOLS,
        manual: bool = MANUAL,
        output: Annotated[TextIO, typer.Argument(hidden=True, parser=_get_output)] = sys.stdout
    ):
    if manual and not GIT_LLM_ON:
        return

    folder = '.'
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
            respository_description=lambda: _get_description(
                file_path
            ) # type: ignore
        )
        for message in client.message(changes, stream=False):
            if with_comments:
                if not commented:
                    print('# ', end='', file=output)
                    commented = True
                for c in message:
                    print(c, end='', file=output)
                    if c == '\n':
                        print('# ', end='', file=output)
            else:
                print(message, end='', file=output)
        print(file=output)
    else:
        print("No changes", file=output)

@app.command(help="Reads the configuration value")
def get_config(setting: Setting, scope : Scope = Scope.LOCAL):
    config = _get_config(setting.value)
    if config:
        print(config, end='')
    else:
        print(f'{DEFAULT_SETTINGS[setting]} [default-value]')

@app.command(help="Sets the configuration setting value, if no value is given resets the configuration to the default value")
def set_config(setting: Setting, value : str | None = None, scope : Scope = Scope.LOCAL):
    if value:
        _set_config(setting.value, value, scope=scope)
    else:
        unset_config(setting.value, scope=scope)

if __name__ == "__main__":
    app()
