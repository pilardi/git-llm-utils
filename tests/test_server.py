from flask import Flask, jsonify, request
from git_llm_utils.utils import (
    _bool,
    execute_command,
    execute_background_command,
    read_file,
)
from git_llm_utils.main import COMMIT_ALIAS, COMMIT_ALIAS_GIT_COMMAND
from pathlib import Path
from typing import Callable, Optional
import os
import pytest
import signal
import sys
import time

API_KEY_TOKEN = "test"

app = Flask(__name__)


def _read_file(file_path, base_path: str = os.getcwd()) -> Optional[str]:
    return read_file(file_path=Path(f"{base_path}/{file_path}"))


def _require_token_bearer(auth_token: str = API_KEY_TOKEN):
    """
    Requires the given bearer auth header in the request
    """

    def decorate(f: Callable):
        def auth(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return "Not Authorization", 401
            parts = auth_header.split()
            if parts[0].lower() != "bearer" or len(parts) == 1 or len(parts) > 2:
                return "Invalid Authorization", 401
            token = parts[1]
            if token != auth_token:
                return "Unauthorized Token", 403
            return f(*args, **kwargs)

        return auth

    return decorate


@app.route("/chat/completions", methods=["POST"])  # type: ignore
@_require_token_bearer()
def mock_chat_completions():
    data = request.json
    messages = data.get("messages", [])
    last_message = messages and messages[-1].get("content", "") or None
    prefix = "Test Changes:"
    system = messages and messages[0].get("content", "") or ""
    if "✅" in system:
        prefix = f"✅{prefix}"
    test_response = (
        last_message and f"{prefix}\n{last_message}" or "What are the changes?"
    )
    if data.get("stream"):

        def generate_stream():
            for char in test_response:
                time.sleep(0.01)
                yield f"data: {jsonify({'choices': [{'delta': {'content': char}}]}).get_data(as_text=True)}\n\n"
            yield "data: [DONE]\n\n"

        return app.response_class(generate_stream(), mimetype="text/event-stream")
    else:
        id = int(time.time())
        return jsonify(
            {
                "id": f"test-model-response-{id}",
                "object": "chat.completion",
                "created": id,
                "model": "mock-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": test_response,
                        },
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
            }
        )


def _start_mock_server(port: int = 8001, debug: bool = False):
    print(f"Starting Mock Server on port: {port}, debug={debug}")
    app.run(
        port=port,
        debug=debug,
    )


@pytest.fixture(scope="session")
def mock_server(request):
    def shudown_server(process):
        print("Stopping Mock server")
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            pass

    print("Starting Mock server")
    port = 8001  # REVIEW we might want to select an open port
    process = execute_background_command(["uv", "run", "python", __file__, str(port)])
    time.sleep(1)
    if process.poll() is not None:  # type: ignore
        stdout, stderr = process.communicate()  # type: ignore
        raise RuntimeError(
            f"Server failed to start mock server: {stdout.decode()}/{stderr.decode()}"
        )
    request.addfinalizer(lambda: shudown_server(process))
    return f"http://127.0.0.1:{port}"


@pytest.fixture(scope="session")
def cmd(request):
    return request.config.getoption("--cmd").split() + ["--no-confirm"]


@pytest.fixture(scope="session")
def repository(tmp_path_factory):
    repository = tmp_path_factory.mktemp("repository")
    execute_command(["git", "init", "."], cwd=repository)
    execute_command(["cp", f"{os.getcwd()}/tests/files/test.txt", "."], cwd=repository)
    execute_command(["git", "add", "test.txt"], cwd=repository)
    return repository


@pytest.fixture(scope="session")
def repository_2(tmp_path_factory):
    repository = tmp_path_factory.mktemp("repository")
    execute_command(["git", "init", "."], cwd=repository)
    execute_command(["cp", f"{os.getcwd()}/tests/files/test.txt", "."], cwd=repository)
    execute_command(["git", "add", "test.txt"], cwd=repository)
    return repository


@pytest.mark.integration
def test_status_with_no_emojis(cmd, repository, mock_server):
    status = _read_file("tests/files/status.out")
    args = cmd + [
        "status",
        "--api-url",
        mock_server,
        "--model",
        "openai/test",
        "--api-key",
        API_KEY_TOKEN,
        "--no-with-emojis",
    ]
    assert status == execute_command(
        args,
        cwd=repository,
    )
    execute_command(  # update settings
        cmd + ["set-config", "emojis", "--scope", "local", "--value", "False"],
        cwd=repository,
    )
    del args[-1]
    assert status == execute_command(
        args,
        cwd=repository,
    )


@pytest.mark.integration
def test_status_with_emojis(cmd, repository, mock_server):
    status = _read_file("tests/files/status_with_emojis.out")
    args = cmd + [
        "status",
        "--api-url",
        mock_server,
        "--model",
        "openai/test",
        "--api-key",
        API_KEY_TOKEN,
        "--with-emojis",
    ]
    assert status == execute_command(
        args,
        cwd=repository,
    )
    execute_command(  # update settings
        cmd + ["set-config", "emojis", "--scope", "local", "--value", "True"],
        cwd=repository,
    )
    del args[-1]
    assert status == execute_command(
        args,
        cwd=repository,
    )


@pytest.mark.integration
def test_generate_with_no_comments(cmd, repository, mock_server):
    status = _read_file("tests/files/generate_with_no_comments.out")
    args = cmd + [
        "generate",
        "--api-url",
        mock_server,
        "--model",
        "openai/test",
        "--api-key",
        API_KEY_TOKEN,
        "--no-manual",
        "--no-with-comments",
    ]
    assert status == execute_command(
        args,
        cwd=repository,
    )
    execute_command(  # update settings
        cmd + ["set-config", "comments", "--scope", "local", "--value", "False"],
        cwd=repository,
    )
    del args[-1]
    assert status == execute_command(
        args,
        cwd=repository,
    )


@pytest.mark.integration
def test_generate_with_comments(cmd, repository, mock_server):
    status = _read_file("tests/files/generate_with_comments.out")
    args = cmd + [
        "generate",
        "--api-url",
        mock_server,
        "--model",
        "openai/test",
        "--api-key",
        API_KEY_TOKEN,
        "--no-manual",
        "--with-comments",
    ]
    assert status == execute_command(
        args,
        cwd=repository,
    )
    execute_command(  # update settings
        cmd + ["set-config", "comments", "--scope", "local", "--value", "True"],
        cwd=repository,
    )
    del args[-1]
    assert status == execute_command(
        args,
        cwd=repository,
    )


@pytest.mark.integration
def test_generate_with_comments_and_repository(
    cmd, repository, repository_2, mock_server
):
    status = _read_file("tests/files/generate_with_comments.out")
    args = cmd + [
        "--repository",
        repository,
        "generate",
        "--api-url",
        mock_server,
        "--model",
        "openai/test",
        "--api-key",
        API_KEY_TOKEN,
        "--no-manual",
        "--with-comments",
    ]
    assert status == execute_command(args)
    execute_command(  # update settings
        cmd
        + [
            "--repository",
            repository,
            "set-config",
            "comments",
            "--scope",
            "local",
            "--value",
            "True",
        ]
    )
    del args[-1]
    assert status == execute_command(args)
    assert status == execute_command(args, repository_2)


@pytest.mark.integration
def test_install_alias(cmd, repository, repository_2):
    execute_command(
        cmd
        + [
            "--repository",
            repository,
            "install-alias",
        ]
    )
    output = execute_command(
        ["git", "config", "--get", f"alias.{COMMIT_ALIAS}"], cwd=repository
    )
    assert COMMIT_ALIAS_GIT_COMMAND == (output is not None and output.strip() or None)

    execute_command(
        cmd
        + [
            "install-alias",
        ],
        cwd=repository_2,
    )
    output = execute_command(
        ["git", "config", "--get", f"alias.{COMMIT_ALIAS}"], cwd=repository_2
    )
    assert COMMIT_ALIAS_GIT_COMMAND == (output is not None and output.strip() or None)


@pytest.mark.integration
def test_install_alias_command(cmd, repository):
    execute_command(
        cmd + ["--repository", repository, "install-alias", "--command", "integration"]
    )
    output = execute_command(
        ["git", "config", "--get", "alias.integration"], cwd=repository
    )
    assert COMMIT_ALIAS_GIT_COMMAND == (output is not None and output.strip() or None)


@pytest.mark.integration
def test_install_hook(cmd, repository):
    def verify():
        hook = _read_file(".git/hooks/prepare-commit-msg", base_path=repository)
        cli = [] + cmd
        del cli[-1]  # removes confirm setting
        assert hook is not None
        if cmd[0] != "uv":  # we are verifying the binary as uv env is dynamic
            assert " ".join(cli) in hook

    execute_command(cmd + ["--repository", repository, "install-hook"])
    verify()

    execute_command(cmd + ["--repository", repository, "install-hook", "--overwrite"])
    verify()


@pytest.mark.integration
def test_install(cmd, repository):
    execute_command(
        cmd
        + [
            "--repository",
            repository,
            "install",
            "--overwrite",
            "--command",
            "llmc-installed",
        ]
    )
    hook = _read_file(".git/hooks/prepare-commit-msg", base_path=repository)
    cli = [] + cmd
    del cli[-1]  # removes confirm setting
    assert hook is not None
    if (
        cmd[0] != "uv"
    ):  # we are verifying the installable only as uv env location is dynamic otherwise
        assert " ".join(cli) in hook

    output = execute_command(
        ["git", "config", "--get", "alias.llmc-installed"], cwd=repository
    )
    assert COMMIT_ALIAS_GIT_COMMAND == (output is not None and output.strip() or None)


if __name__ == "__main__":
    print("Starting mock server")
    _start_mock_server(
        port=len(sys.argv) > 1 and int(sys.argv[1]) or 8001,
        debug=_bool(os.environ.get("DEBUG", "False")),
    )
