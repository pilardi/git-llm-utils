from flask import Flask, jsonify, request
from git_llm_utils.utils import _bool, execute_command
import os
import pytest
import sys
import time

app = Flask(__name__)


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


@pytest.mark.integration
def test_integration(tmp_path):
    """
    TODO
        @uv run python tests/test_server.py &
        SERVER_ID=$$!
        @WORK_DIR=$$(pwd)
        @TEMP_DIR=$$(mktemp -d)
        cd $${TEMP_DIR} && git init . && echo "test" > test.txt && git add test.txt
        $${WORK_DIR}/dist/git-llm-utils status --api-url http://127.0.0.1:8001 --model openai/test --api-key test > status.out
        $${WORK_DIR}/dist/git-llm-utils generate --api-url http://127.0.0.1:8001 --model openai/test --api-key test --no-manual > generate.out
        $${WORK_DIR}/dist/git-llm-utils generate --api-url http://127.0.0.1:8001 --model openai/test --api-key test --no-manual --with-comments > generate-comments.out
        GIT_LLM_UTILS_REPO="$${TEMP_DIR}" && uv --directory "$${WORK_DIR}" run pytest -m "integration"
        kill $${SERVER_ID}
    """
    if not tmp_path:
        pytest.fail(f"integration tests need a test path for creating the repository")
    repository = tmp_path
    print(f"Testing {repository}")
    # print(execute_command(["dist/git-llm-utils", "--help"], cwd=repository))


if __name__ == "__main__":
    app.run(
        port=len(sys.argv) > 1 and int(sys.argv[1]) or 8001,
        debug=_bool(os.environ.get("DEBUG", "False")),
    )
