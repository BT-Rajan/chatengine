"""
server.py — optional thin HTTP layer exposing POST /api/chat, matching
the request/response shape of the original JDK Smart Factory endpoint:

  POST /api/chat
  { "message": "...", "history": [{"role": "user"/"assistant", "content": "..."}] }

  -> { "ok": true, "reply": "...", "sql": "...", "row_count": N }

Run directly with `python -m db_chat_ai.server`, or import `create_app()`
into an existing Flask app.
"""

from flask import Flask, jsonify, request

from .chat_engine import DBChat


def create_app() -> Flask:
    app = Flask(__name__)
    chat = DBChat()

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        body = request.get_json(silent=True) or {}
        message = body.get("message", "")
        history = body.get("history", [])

        response = chat.ask(message, history=history)
        payload = {
            "ok": response.error is None,
            "reply": response.reply,
            "sql": response.sql,
            "row_count": response.row_count,
        }
        if response.error:
            payload["error"] = response.error
        status = 200 if response.error not in ("llm_error", "sql_execution_error") else 502
        return jsonify(payload), status

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"ok": True})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5001, debug=False)
