# db-chat-ai

A standalone, natural-language chat library that answers questions about
any combination of a database, local files (`.md` / `.txt` / `.csv`), and
web pages — built as a lightweight, enterprise-extensible RAG engine.
Originally extracted from the JDK Smart Factory app's `/api/chat` feature,
then generalized to any data source, then refactored into the
plugin/feature-flag architecture described below.

Nothing here requires embeddings, a vector database, or a heavy framework.
Every advanced capability (embedding search, reranking, caching,
conversation memory, new data-source plugins) is **off by default**,
**zero-cost when off**, and enabled purely by editing `ai-conf.py`.

---

## Architecture

```
                     ┌───────────────────────────┐
   ai-conf.py  ───▶  │   AIConfig (config.py)    │
 (feature flags,     └─────────────┬─────────────┘
  plugin flags,                    │
  style prompt)                    ▼
                     ┌───────────────────────────┐
                     │        DBChat              │  chat_engine.py
                     │  (plan → gather → answer)  │
                     └──┬───────┬───────┬───────┬─┘
                        │       │       │       │
              ┌─────────┘   ┌───┘   ┌───┘   ┌───┘
              ▼             ▼       ▼       ▼
        ┌──────────┐  ┌──────────┐ ┌──────┐ ┌──────┐
        │ Plugins  │  │ Retriever│ │Cache │ │Memory│   ◀── interfaces/
        │(sql/csv/ │  │(keyword/ │ │(none/│ │(none/│       + factories/
        │ docs/web)│  │ embed/   │ │memory│ │ in-  │       resolve config
        │          │  │ hybrid)  │ │/redis│ │memory│       into concrete
        └────┬─────┘  └──────────┘ └──────┘ └──────┘       implementations
             │                                    ▲
             ▼                                    │
        ┌──────────┐                        ┌───────────┐
        │ Reranker │ ◀── reorders retrieved  │  Plan/answer
        │(none/    │     document chunks     │  LLM calls
        │ cross-   │     before the answer   │(llm_client.py)
        │ encoder) │     step                └───────────┘
        └──────────┘
```

`chat_engine.py` never imports a specific plugin, retriever, cache, or
memory implementation — it only knows the `Plugin` / `Retriever` /
`Cache` / `Memory` / `Reranker` interfaces (`interfaces/`). The factories
(`factories/`) are the only code that turns `ai-conf.py` settings into
concrete objects. That's the extension point: a new plugin, a real
embedding retriever, or a real reranker gets added by writing one class
and registering it in one factory — `chat_engine.py` never changes.

## Directory structure

```
ai-conf.py                    AI key/model + FEATURES + PLUGINS + STYLE_PROMPT
db_chat_ai/
  chat_engine.py               plan -> gather -> answer orchestration (DBChat)
  config.py                    loads ai-conf.py into an AIConfig
  connector.py                 generic SQLAlchemy engine for the sql plugin
  schema.py                    schema + sample-row introspection (sql & csv)
  sql_guard.py                 read-only SQL validation
  llm_client.py                DeepSeek-compatible chat-completions call
  server.py                    optional Flask wrapper (POST /api/chat)

  interfaces/                  abstract contracts — no concrete logic
    plugin.py                   Plugin (kind: "sql" | "document")
    retriever.py                 Retriever, KeywordRetriever (real),
                                  EmbeddingRetriever/HybridRetriever (placeholders)
    memory.py                    Memory, NoMemory (real), InMemorySessionMemory (real)
    cache.py                     Cache, NoCache/MemoryCache (real), RedisCache (real,
                                  lazy-imports redis)
    reranker.py                  Reranker, NoReranker (real),
                                  FutureCrossEncoderReranker (placeholder)

  factories/                    config -> concrete implementation
    plugin_loader.py             PLUGIN_REGISTRY + load_plugins()
    retriever_factory.py         RetrieverFactory
    memory_factory.py            MemoryFactory
    cache_factory.py             CacheFactory
    reranker_factory.py          RerankerFactory

  plugins/                      one file per data source
    mysql.py                     "sql" plugin — any SQLAlchemy DB (name is historical)
    csv.py                       "csv" plugin — .csv files as queryable tables
    documents.py                  "documents" plugin — .md/.txt files
    website.py                    "website" plugin — WEB_URLS
    _template.py                  copy this to add a new plugin (not loaded)

  sources/                      low-level loaders used by plugins
    csv_tables.py                 loads .csv into an in-memory SQLite engine
    documents.py                  loads/chunks .md/.txt/web text, keyword search

example_usage.py               minimal REPL example
requirements.txt               core + clearly-marked optional dependencies
```

## Feature flags

All in `ai-conf.py`, all default to the lightest-weight option:

```python
FEATURES = {
    "keyword_search": True,       # document/website search by keyword overlap
    "embedding_search": False,    # reserved — raises clearly if turned on;
                                   # see interfaces/retriever.py
    "reranker": False,            # reserved — see interfaces/reranker.py
    "conversation_memory": False, # server-side session history
    "cache": False,               # cache answers by (session, question)
}
```

Turning a feature off means its code path — and its optional dependency,
if it has one — is never touched. `embedding_search` and `reranker` are
**provisioned, not implemented**: enabling them without wiring a real
model raises a clear `NotImplementedError`-based error rather than
silently behaving like the feature does nothing, so a misconfiguration
never looks like "no results found".

## Plugins (data sources)

```python
PLUGINS = {
    "sql": True,        # a real database, via DB_URL
    "csv": False,       # .csv files in FILES, loaded as queryable tables
    "documents": False, # .md/.txt files in FILES, searched for passages
    "website": False,   # pages in WEB_URLS, searched the same way
}
```

Any combination is valid. A disabled plugin is never imported — so a
missing optional dependency for a disabled plugin (e.g. no `pandas`
installed and `csv` is off) can never break startup. If an **enabled**
plugin fails to load (missing dependency, bad config, unreachable
service), only that plugin is skipped, with a `warnings.warn(...)` — every
other plugin keeps working. Verified in testing: disabling `csv` with
`pandas` unavailable starts cleanly; enabling `csv` with `pandas`
unavailable degrades to zero plugins loaded with a warning, no crash.

### Writing a new plugin

Copy `db_chat_ai/plugins/_template.py`, implement `describe()` / `search()`
/ `kind`, register it in `PLUGIN_REGISTRY` in
`db_chat_ai/factories/plugin_loader.py`, and add its flag to `PLUGINS` in
`ai-conf.py`. No other file changes. This is how `sharepoint`, `github`,
`confluence`, or any other future source gets added.

## Writing a new retriever / cache implementation

Same pattern: subclass `Retriever` (or `Cache`) in `interfaces/`, wire it
into the matching factory (`RetrieverFactory` / `CacheFactory`), and
select it via config (`FEATURES["embedding_search"]`, `CACHE["type"]`).
`chat_engine.py` and every plugin are unaffected.

## Conversation memory, caching, reranking

These are **infrastructure, not sophistication** — deliberately, per the
design brief:

- **Memory** (`FEATURES["conversation_memory"]`): a `session_id` you pass
  to `chat.ask()` gets its history stored in-process
  (`InMemorySessionMemory`, capped at `MEMORY["max_turns"]`) and merged in
  automatically on the next call with that session — no summarization, no
  relevance ranking, just a bounded ring buffer. Swap in a
  database/Redis-backed `Memory` for persistence across restarts; the
  interface is identical.
- **Cache** (`FEATURES["cache"]`): answers are cached by
  `(session_id, question)`. `CACHE["type"]` picks `"memory"` (no
  dependency) or `"redis"` (imports `redis` lazily, only when this
  combination is actually selected).
- **Reranker** (`FEATURES["reranker"]`): reorders retrieved document
  chunks before the answer step. `NoReranker` (default) is a pass-through;
  `FutureCrossEncoderReranker` is a reserved, unimplemented placeholder.

## Setup

```bash
pip install -r requirements.txt
```

Configure everything in `ai-conf.py` (env vars of the same name override
the file — see comments inside it):

```python
DEEPSEEK_API_KEY = "sk-..."
PLUGINS = {"sql": True, "csv": False, "documents": True, "website": False}
DB_URL = "mysql+pymysql://user:pass@localhost:3306/your_db"
FILES = ["./docs"]
STYLE_PROMPT = """Answer like a friendly support rep, 2-3 sentences."""
```

**Recommended:** if using `sql`, point `DB_URL` at a database user with
`SELECT`-only grants — the library already blocks any non-`SELECT`
statement, but a read-only DB user is a solid second layer of defense.

## Use as a library — in any app

```python
from db_chat_ai import DBChat

chat = DBChat()
response = chat.ask("how many open orders does Acme have?")
print(response.reply)

# optional: server-side session memory (requires FEATURES["conversation_memory"])
response = chat.ask("what about last week?", session_id="user-42")
```

`DBChat()` reads `ai-conf.py` once at construction and adapts to whatever
plugins/features are turned on — calling code never needs to know which
ones are active. Pass a custom `AIConfig` instead of relying on
`ai-conf.py` to embed multiple independently-configured chat instances in
one app (e.g. one per tenant).

`response` fields: `reply`, `sql`, `rows`, `row_count`, `doc_query`,
`doc_sources`, `error` (`None` on success), `from_cache` (`True` if this
exact question/session was served from cache).

## Use as a drop-in HTTP endpoint

```bash
python -m db_chat_ai.server
```

Exposes `POST /api/chat`, unchanged shape:

```json
// request
{"message": "what's your refund policy", "history": []}
// response
{"ok": true, "reply": "Refunds are accepted within 30 days of purchase.", "sql": null, "row_count": null}
```

## Migration notes (pre-refactor → this version)

- **Fully backward compatible.** An `ai-conf.py` written before this
  refactor (using `SOURCES = {"db": ..., "files": ..., "web": ...}`)
  still loads and behaves identically — `config.py` detects the absence
  of `PLUGINS`/`FEATURES` and derives them from the old `SOURCES` shape.
  Verified in testing.
- `DBChat.ask(message, history)` is unchanged. One new optional parameter,
  `session_id`, was added at the end — existing calls are unaffected.
- Internally, the old single `chat_engine.py` monolith (DB schema +
  document search inlined) was split into `interfaces/` (contracts),
  `factories/` (config → implementation), and `plugins/` (one file per
  data source), per the deliverable's SOLID/composition requirements.
- The old `sql_source` planning values `"db"` / `"csv"` are now `"sql"` /
  `"csv"` (matching plugin names) — an internal prompt detail, not part
  of the public `ChatResponse` shape.

## Optional dependencies

| Dependency | Required for | Otherwise |
|---|---|---|
| `pandas` | `PLUGINS["csv"] = True` | never imported; csv plugin skipped with a warning if enabled without it |
| `redis` | `FEATURES["cache"]` + `CACHE["type"] = "redis"` | never imported for any other configuration |

`SQLAlchemy`, `PyMySQL`, and `Flask` are the only always-required
dependencies (`Flask` only if you use `server.py`).

## Design decisions

- **Interfaces over inheritance-heavy hierarchies**: every optional
  component (`Plugin`, `Retriever`, `Memory`, `Cache`, `Reranker`) is a
  small ABC with one or two methods, composed into `DBChat` via
  constructor injection from factories — never a deep class hierarchy.
- **Fail loud, not silent, for unimplemented placeholders**:
  `EmbeddingRetriever` / `FutureCrossEncoderReranker` raise
  `NotImplementedError` if actually invoked, rather than quietly acting
  like the feature does nothing — a wrong config surfaces immediately.
- **Fail soft, not silent, for plugin loading**: an enabled plugin that
  can't load (bad dependency, bad config) is skipped with a `warnings.warn`
  and the rest of the app keeps working — one bad data source shouldn't
  take down every other one.
- **No new mandatory dependencies**: `pandas` and `redis` are imported
  only inside the one class that needs them, only reached when that
  exact feature is both enabled and selected.
- **`ai-conf.py` stays the single config surface**: rather than
  introducing YAML (an extra mandatory dependency for a lightweight
  project), feature flags and plugin flags are plain Python dicts in the
  same file that already held `STYLE_PROMPT` and the AI connection
  settings — one file to edit, no new format to learn.
- **Backward compatibility over a clean break**: the old `SOURCES` config
  shape is derived into the new `PLUGINS` shape automatically rather than
  requiring every existing deployment to rewrite its config.

## Other limitations

- Document relevance search (`KeywordRetriever`) is a simple
  keyword-overlap ranking over paragraph-sized chunks — no
  embeddings/vector DB, which keeps this a plain `pip install` library.
  Works well for FAQs/notes/moderate documentation; not a substitute for
  real vector search over large document collections. `embedding_search`
  and `reranker` are the reserved extension points for that.
- Schema, CSV tables, and loaded documents are cached at plugin
  construction. Call `chat.refresh_sources()` if files on disk change,
  `ai-conf.py`'s `FILES`/`WEB_URLS` are edited, or the database schema
  changes at runtime.
- `InMemorySessionMemory` and `MemoryCache` are per-process, not shared
  across multiple app instances/workers — use `RedisCache` (already
  provided) or a custom database-backed `Memory` for that.
