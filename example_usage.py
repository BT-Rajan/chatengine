"""
Minimal example of using db-chat-ai directly as a library (no HTTP server).

Everything about which data it can see (plugins: sql / csv / documents /
website), which optional features are on (embedding search, reranking,
caching, conversation memory), and how it sounds (tone, persona, length)
is controlled in ai-conf.py — this script itself never changes.

    export DEEPSEEK_API_KEY="sk-..."
(or edit ai-conf.py directly)
"""

from db_chat_ai import DBChat

chat = DBChat()

# A session_id is optional — pass one if FEATURES["conversation_memory"] is
# enabled in ai-conf.py and you want the library to remember this
# conversation across calls without you having to pass `history` yourself.
SESSION_ID = "local-repl"

while True:
    question = input("\nAsk about your data (or 'quit'): ").strip()
    if question.lower() in ("quit", "exit"):
        break

    response = chat.ask(question, session_id=SESSION_ID)
    print(f"\n{response.reply}")
    if response.sql:
        print(f"\n[debug] SQL used: {response.sql}")
    if response.doc_sources:
        print(f"[debug] pulled from: {', '.join(response.doc_sources)}")
    if response.from_cache:
        print("[debug] (served from cache)")
