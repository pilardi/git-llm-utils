from typing import Optional, Tuple
from llm_cli import LLMClient

import os
import subprocess
import typer

app = typer.Typer()

FOLDER = typer.Option(is_flag=False, default='.', help="folder with git repo and staged changes")
WITH_EMOJIS = typer.Option(is_flag=True, default=True, help="If true will instruct the LLMs to add applicable emojis")
MODEL = typer.Option(is_flag=True, default="qwen3-coder:480b-cloud", help="The model to use (has to be available)")

def _execute_command(command: list[str]) -> Tuple[str, Optional[str]]:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            encoding="utf-8",
            errors="replace",
        )
        return process.stdout, None
    except subprocess.CalledProcessError as e:
        return None, e.stderr # type: ignore

def get_staged_changes(folder : str) -> Optional[str]:
    """
    Generate diff message from the staged changes
    Returns:
        Optional[str]: the changes or empty if there weren't any
    """
    output, error = _execute_command(["git", "diff", "--staged", folder])
    if error:
        print(f"Error in executing git diff command: {error}")
        raise Exception(f"Failed to execute git command: {error}")
    return output

@app.command(help="Generates a commit message based on the git staged changes")
def status(folder : str = FOLDER, with_emojis : bool = WITH_EMOJIS, model : str = MODEL):
    changes = get_staged_changes(folder=folder)
    if changes:
        for message in LLMClient(model_name=model, use_emojis=with_emojis).message(changes, stream=True):
            print(message, end='')
        print()
    else:
        print("No changes")

if __name__ == "__main__":
    app()
