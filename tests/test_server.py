from flask import Flask, jsonify, request
from git_llm_utils.utils import _bool, execute_command, execute_background_command
import os
import pytest
import signal
import sys
import time

app = Flask(__name__)


def _read_file(file_path):
    with open(f"{os.getcwd()}/{file_path}", "r") as f:
        return f.read()


@app.route("/chat/completions", methods=["POST"])
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
def cmd():
    return f"{os.getcwd()}/dist/git-llm-utils"


@pytest.fixture(scope="session")
def repository(tmp_path_factory):
    repository = tmp_path_factory.mktemp("repository")
    print(execute_command(["git", "init", "."], cwd=repository))
    print(
        execute_command(
            ["cp", f"{os.getcwd()}/tests/files/test.txt", "."], cwd=repository
        )
    )
    print(execute_command(["git", "add", "test.txt"], cwd=repository))
    return repository


@pytest.mark.integration
def test_status(cmd, repository, mock_server):
    output = execute_command(
        [
            cmd,
            "status",
            "--api-url",
            mock_server,
            "--model",
            "openai/test",
            "--api-key",
            "test",
            "--no-with-emojis",
        ],
        cwd=repository,
    )
    assert _read_file("tests/files/status.out") == output


@pytest.mark.integration
def test_status_with_emojis(cmd, repository, mock_server):
    output = execute_command(
        [
            cmd,
            "status",
            "--api-url",
            mock_server,
            "--model",
            "openai/test",
            "--api-key",
            "test",
            "--with-emojis",
        ],
        cwd=repository,
    )
    assert _read_file("tests/files/status_with_emojis.out") == output


@pytest.mark.integration
def test_generate_with_no_comments(cmd, repository, mock_server):
    output = execute_command(
        [
            cmd,
            "generate",
            "--api-url",
            mock_server,
            "--model",
            "openai/test",
            "--api-key",
            "test",
            "--no-manual",
            "--no-with-comments",
        ],
        cwd=repository,
    )
    assert _read_file("tests/files/generate_with_no_comments.out") == output


@pytest.mark.integration
def test_generate_with_comments(cmd, repository, mock_server):
    output = execute_command(
        [
            cmd,
            "generate",
            "--api-url",
            mock_server,
            "--model",
            "openai/test",
            "--api-key",
            "test",
            "--no-manual",
            "--with-comments",
        ],
        cwd=repository,
    )
    assert _read_file("tests/files/generate_with_comments.out") == output


if __name__ == "__main__":
    _start_mock_server(
        port=len(sys.argv) > 1 and int(sys.argv[1]) or 8001,
        debug=_bool(os.environ.get("DEBUG", "False")),
    )
