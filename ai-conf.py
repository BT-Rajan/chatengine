"""
ai-conf.py — AI + feature + data-source provisioning for db-chat-ai.

This is the ONE file you edit to point the library at your data, choose
which optional capabilities are on, and set your AI provider. Everything
below can also be supplied via an environment variable of the same name
(env wins over this file), so this file can be committed with blanks /
defaults and real values injected at deploy time.

Nothing in this file is mandatory except DEEPSEEK_API_KEY and at least
one enabled entry in PLUGINS — every other setting has a safe, inert
default, and turning a feature off means its code path (and its optional
dependency, if it has one) is never touched.
"""

import os

# ── AI connection (required) ─────────────────────────────────────────────────
DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# ── Behavior tuning ───────────────────────────────────────────────────────────
MAX_TOKENS: int = int(os.environ.get("AI_MAX_TOKENS", "700"))
TEMPERATURE: float = float(os.environ.get("AI_TEMPERATURE", "0.2"))
REQUEST_TIMEOUT_SECONDS: int = int(os.environ.get("AI_TIMEOUT", "30"))
MAX_HISTORY_TURNS: int = int(os.environ.get("AI_MAX_HISTORY_TURNS", "10"))

# ── Feature flags ─────────────────────────────────────────────────────────────
# Every entry defaults to the lightest-weight option. Flipping one on is the
# only thing that ever activates its code path or its optional dependency.
FEATURES: dict = {
    "keyword_search": True,       # search documents/website plugins by keyword overlap
    "embedding_search": False,    # reserved — see db_chat_ai/interfaces/retriever.py
    "reranker": False,            # reserved — see db_chat_ai/interfaces/reranker.py
    "conversation_memory": False, # server-side session history (see MEMORY below)
    "cache": False,               # cache answers by (session, question) (see CACHE below)
}

# ── Plugins — one flag per data source; any combination is valid ────────────
# "sql"       — query a real database (SQL is generated and validated for you)
# "csv"       — load .csv files from FILES as queryable tables (same SQL path)
# "documents" — load .md / .txt files from FILES, searched for relevant passages
# "website"   — pull content from WEB_URLS, searched the same way as documents
# New plugins (sharepoint, github, confluence, ...) register in
# db_chat_ai/factories/plugin_loader.py — see plugins/_template.py.
PLUGINS: dict = {
    "sql": True,
    "csv": False,
    "documents": False,
    "website": False,
}

# ── "sql" plugin config (only used if PLUGINS["sql"] is True) ───────────────
# One connection string, e.g.:
#   "mysql+pymysql://user:pass@localhost:3306/dbname"
#   "postgresql://user:pass@host:5432/dbname"
#   "sqlite:///path/to/file.db"
# Leave blank to fall back to DB_URL / DB_HOST+DB_NAME+... env vars (see
# db_chat_ai/connector.py) for continuity with the original app's settings.
DB_URL: str = os.environ.get("DB_URL", "")
MAX_ROWS_RETURNED: int = int(os.environ.get("AI_MAX_ROWS", "200"))
MAX_SAMPLE_ROWS_PER_TABLE: int = int(os.environ.get("AI_SCHEMA_SAMPLE_ROWS", "3"))

# ── "csv" / "documents" plugin config (only used if enabled above) ──────────
# Each entry can be a single file or a folder (folders are scanned
# recursively). .csv files feed the "csv" plugin; .md/.txt files feed the
# "documents" plugin — both read from this same list.
FILES: list = [
    # "./docs",
    # "./notes.md",
    # "./data/customers.csv",
]

# ── "website" plugin config (only used if PLUGINS["website"] is True) ───────
WEB_URLS: list = [
    # "https://example.com/faq",
]

# How many document/paragraph snippets (from documents + website combined)
# to pull into context per question, and how large each chunk is when a
# document gets split up for relevance search.
DOC_TOP_K: int = int(os.environ.get("AI_DOC_TOP_K", "5"))
DOC_CHUNK_CHARS: int = int(os.environ.get("AI_DOC_CHUNK_CHARS", "1200"))
WEB_FETCH_TIMEOUT_SECONDS: int = int(os.environ.get("AI_WEB_TIMEOUT", "15"))

# ── "conversation_memory" config (only used if FEATURES["conversation_memory"]) ──
MEMORY: dict = {
    "max_turns": 10,
}

# ── "cache" config (only used if FEATURES["cache"] is True) ─────────────────
CACHE: dict = {
    "type": "memory",  # "memory" (no dependency) | "redis" (needs `pip install redis`)
    "redis_url": os.environ.get("CACHE_REDIS_URL", "redis://localhost:6379/0"),
}

# ── "reranker" config (only used if FEATURES["reranker"] is True) ───────────
RERANKER: dict = {
    "type": "none",  # "none" (no-op) | "cross_encoder" (not implemented yet — reserved)
}

# ── Tone / style ──────────────────────────────────────────────────────────────
# This is the ONLY thing that controls how answers sound. Change it freely —
# formal, casual, a specific persona, a target reading level, a required
# language, whatever your app needs. It's used verbatim as part of the
# system prompt for the final answer step.
STYLE_PROMPT: str = """Answer in plain, everyday language. Keep it short —
1 to 3 sentences, or a brief list if there are several items. Lead with the
number or the direct answer. Never tell the person to go check the data
themselves — you already have it in front of you."""
