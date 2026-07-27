"""
config.py — loads settings from ai-conf.py.

ai-conf.py is deliberately named with a hyphen (matching the original
request) so it reads as a config file rather than an importable module —
it's loaded here by file path instead of a normal `import`, and env vars
set on the process always win.

Backward compatibility: this refactor introduced PLUGINS (sql/documents/
csv/website, one flag per plugin) as the successor to the older SOURCES
dict (db/files/web, one flag per source category). Any ai-conf.py written
for the older shape keeps working unchanged — see _derive_plugins_from_sources.
"""

import importlib.util
import os
from dataclasses import dataclass, field
from functools import lru_cache

_DEFAULT_CONF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai-conf.py"
)

_DEFAULT_STYLE_PROMPT = (
    "Answer in plain, everyday language. Keep it short — 1 to 3 sentences, "
    "or a brief list if there are several items. Lead with the number or "
    "the direct answer."
)

_DEFAULT_FEATURES = {
    "keyword_search": True,
    "embedding_search": False,
    "reranker": False,
    "conversation_memory": False,
    "cache": False,
}

_DEFAULT_PLUGINS = {
    "sql": True,
    "documents": False,
    "csv": False,
    "website": False,
}


def _derive_plugins_from_sources(sources: dict) -> dict:
    """Maps the pre-refactor SOURCES = {db, files, web} shape onto the
    current PLUGINS = {sql, documents, csv, website} shape, so an
    ai-conf.py written before this refactor still behaves identically —
    its "files" flag used to mean "load both .csv and .md/.txt from
    FILES", which is now the "csv" and "documents" plugins together."""
    return {
        "sql": bool(sources.get("db", True)),
        "documents": bool(sources.get("files", False)),
        "csv": bool(sources.get("files", False)),
        "website": bool(sources.get("web", False)),
    }


@dataclass
class AIConfig:
    api_key: str
    model: str
    base_url: str
    max_tokens: int
    temperature: float
    timeout: int
    max_history_turns: int

    # which plugins (data sources) are active
    plugins: dict = field(default_factory=lambda: dict(_DEFAULT_PLUGINS))

    # sql / csv plugin config
    db_url: str = ""
    max_rows: int = 200
    sample_rows_per_table: int = 3
    files: list = field(default_factory=list)

    # documents / website plugin config
    web_urls: list = field(default_factory=list)
    doc_top_k: int = 5
    doc_chunk_chars: int = 1200
    web_timeout: int = 15

    # feature flags — retriever type, memory, cache, reranker on/off
    features: dict = field(default_factory=lambda: dict(_DEFAULT_FEATURES))
    memory_max_turns: int = 10
    cache_type: str = "memory"      # "memory" | "redis"
    cache_redis_url: str = "redis://localhost:6379/0"
    reranker_type: str = "none"     # "none" | "cross_encoder"

    # tone / style
    style_prompt: str = _DEFAULT_STYLE_PROMPT

    # ── backward-compat conveniences (pre-refactor code may still read these) ──
    @property
    def db_enabled(self) -> bool:
        return bool(self.plugins.get("sql"))

    @property
    def files_enabled(self) -> bool:
        return bool(self.plugins.get("documents") or self.plugins.get("csv"))

    @property
    def web_enabled(self) -> bool:
        return bool(self.plugins.get("website"))


@lru_cache(maxsize=1)
def load_ai_config(conf_path: str | None = None) -> AIConfig:
    path = conf_path or os.environ.get("AI_CONF_PATH", _DEFAULT_CONF_PATH)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"ai-conf.py not found at {path}. Create it (see ai-conf.py in the "
            "project root) or set AI_CONF_PATH to point at your copy."
        )

    spec = importlib.util.spec_from_file_location("ai_conf", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "PLUGINS"):
        plugins = dict(getattr(module, "PLUGINS"))
    elif hasattr(module, "SOURCES"):
        plugins = _derive_plugins_from_sources(dict(getattr(module, "SOURCES")))
    else:
        plugins = dict(_DEFAULT_PLUGINS)

    features = dict(_DEFAULT_FEATURES)
    features.update(getattr(module, "FEATURES", {}))

    memory_conf = getattr(module, "MEMORY", {}) or {}
    cache_conf = getattr(module, "CACHE", {}) or {}
    reranker_conf = getattr(module, "RERANKER", {}) or {}

    return AIConfig(
        api_key=getattr(module, "DEEPSEEK_API_KEY", ""),
        model=getattr(module, "DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=getattr(module, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        max_tokens=getattr(module, "MAX_TOKENS", 700),
        temperature=getattr(module, "TEMPERATURE", 0.2),
        timeout=getattr(module, "REQUEST_TIMEOUT_SECONDS", 30),
        max_history_turns=getattr(module, "MAX_HISTORY_TURNS", 10),
        plugins=plugins,
        db_url=getattr(module, "DB_URL", ""),
        max_rows=getattr(module, "MAX_ROWS_RETURNED", 200),
        sample_rows_per_table=getattr(module, "MAX_SAMPLE_ROWS_PER_TABLE", 3),
        files=list(getattr(module, "FILES", [])),
        web_urls=list(getattr(module, "WEB_URLS", [])),
        doc_top_k=getattr(module, "DOC_TOP_K", 5),
        doc_chunk_chars=getattr(module, "DOC_CHUNK_CHARS", 1200),
        web_timeout=getattr(module, "WEB_FETCH_TIMEOUT_SECONDS", 15),
        features=features,
        memory_max_turns=memory_conf.get("max_turns", 10),
        cache_type=cache_conf.get("type", "memory"),
        cache_redis_url=cache_conf.get("redis_url", "redis://localhost:6379/0"),
        reranker_type=reranker_conf.get("type", "none"),
        style_prompt=getattr(module, "STYLE_PROMPT", _DEFAULT_STYLE_PROMPT) or _DEFAULT_STYLE_PROMPT,
    )


def reset_config_cache() -> None:
    load_ai_config.cache_clear()
