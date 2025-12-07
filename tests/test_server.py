from flask import Flask, jsonify, request
import time
import sys

app = Flask(__name__)


@app.route("/openai/v1/chat/completions", methods=["POST"])
def mock_chat_completions():
    data = request.json
    messages = data.get("messages", [])
    last_message = messages and messages[-1].get("content", "") or None
    test_response = (
        last_message and f"Test Changes: {last_message}" or "What are the changes?"
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


if __name__ == "__main__":
    app.run(port=len(sys.argv) > 1 and int(sys.argv[1]) or 8001)
