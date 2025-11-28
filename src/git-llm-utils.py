from llm_cli import LLMClient
from git_commands import get_config as _get_config, get_staged_changes, set_config as _set_config, unset_config, Scope, _bool
from enum import Enum

import typer

app = typer.Typer()

class Setting(Enum):
    EMOJIS  = "emojis"
    COMMENTS = "comments"
    MODEL   = "model"
    API_KEY = "api_key"
    API_URL = "api_url"

DEFAULT_SETTINGS = {
    Setting.EMOJIS: _get_config(Setting.EMOJIS.value, 'True'),
    Setting.COMMENTS: _get_config(Setting.COMMENTS.value, 'True'),
    Setting.MODEL: _get_config(Setting.MODEL.value, 'ollama/qwen3-coder:480b-cloud'),
    Setting.API_KEY: _get_config(Setting.API_KEY.value, None),
    Setting.API_URL: _get_config(Setting.API_KEY.value, None)
}

EMOJIS = typer.Option(
    is_flag=True,
    default=_bool(DEFAULT_SETTINGS[Setting.EMOJIS].lower()), # type: ignore
    help="If true will instruct the LLMs to add applicable emojis"
)
COMMENTS = typer.Option(
    is_flag=True,
    default=_bool(DEFAULT_SETTINGS[Setting.COMMENTS].lower()), # type: ignore
    help="If true will generate the commit message commented out so that saving will abort the commit"
)
MODEL = typer.Option(
    is_flag=True,
    default=DEFAULT_SETTINGS[Setting.MODEL],
    help="The model to use (has to be available) according to the LiteLLM provider, as in ollama/llama2 or openai/gpt-5-mini"
)
API_KEY = typer.Option(
    is_flag=False,
    default=DEFAULT_SETTINGS[Setting.API_KEY],
    help="The api key to send to the model service (could use env based on the llm provider as in OPENAI_API_KEY)"
)
API_URL = typer.Option(
    is_flag=False,
    default=DEFAULT_SETTINGS[Setting.API_KEY],
    help="The api url if different than the model provider, as in ollama http://localhost:11434 by default"
)

@app.command(help="Generates a commit message based on the git staged changes")
def status(
        with_emojis : bool = EMOJIS,
        with_comments : bool = COMMENTS,
        model : str = MODEL,
        api_key : str | None = API_KEY,
        api_url : str | None = API_URL
    ):
    changes = get_staged_changes(folder='.')
    if changes:
        commented = False
        client = LLMClient(
            model_name=model,
            use_emojis=with_emojis,
            api_key=api_key,
            api_url=api_url
        )
        for message in client.message(changes, stream=False):
            if with_comments:
                if not commented:
                    print('# ', end='')
                    commented = True
                for c in message:
                    print(c, end='')
                    if c == '\n':
                        print('# ', end='')
            else:
                print(message, end='')
        print()
    else:
        print("No changes")

@app.command(help="Reads the configuration value")
def get_config(setting: Setting, scope : Scope = Scope.LOCAL):
    config = _get_config(setting.value, '')
    if config:
        print(config)
    else:
        print(f'{DEFAULT_SETTINGS[setting]} [default-value]')

@app.command(help="Sets the configuration setting value")
def set_config(setting: Setting, value : str, scope : Scope = Scope.LOCAL):
    _set_config(setting.value, value, scope=scope)

@app.command(help="Removes the configuration setting value (will use the default)")
def remove_config(setting: Setting, scope : Scope = Scope.LOCAL):
    unset_config(setting.value, scope=scope)

if __name__ == "__main__":
    app()
