from llm_cli import LLMClient
from git_commands import get_config as _get_config, get_staged_changes, set_config as _set_config, unset_config, Scope, _bool
from enum import Enum

import typer

app = typer.Typer()

class Setting(Enum):
    EMOJIS  = "emojis"
    COMMENTS = "comments"
    MODEL   = "model" 

DEFAULT_SETTINGS = {
    Setting.EMOJIS: _get_config(Setting.EMOJIS.value, 'True'),
    Setting.COMMENTS: _get_config(Setting.COMMENTS.value, 'True'),
    Setting.MODEL: _get_config(Setting.MODEL.value, 'qwen3-coder:480b-cloud')
}

EMOJIS = typer.Option(is_flag=True, default=_bool(DEFAULT_SETTINGS[Setting.EMOJIS].lower()), help="If true will instruct the LLMs to add applicable emojis")
COMMENTS = typer.Option(is_flag=True, default=_bool(DEFAULT_SETTINGS[Setting.COMMENTS].lower()), help="If true will generate the commit message commented out so that saving will abort the commit")
MODEL = typer.Option(is_flag=True, default=DEFAULT_SETTINGS[Setting.MODEL], help="The model to use (has to be available)")

@app.command(help="Generates a commit message based on the git staged changes")
def status(with_emojis : bool = EMOJIS,  with_comments : bool = COMMENTS, model : str = MODEL):
    changes = get_staged_changes(folder='.')
    if changes:
        commented = False
        for message in LLMClient(model_name=model, use_emojis=with_emojis).message(changes, stream=True):
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
