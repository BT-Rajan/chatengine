"""
plugins/_template.py — copy this to add a new plugin (e.g. sharepoint.py,
github.py, confluence.py). Not registered or loaded by default — it's a
starting point, not a real plugin.

Steps to add a new plugin:
  1. Copy this file to plugins/<yourname>.py and implement the class below.
  2. Register it in factories/plugin_loader.py's PLUGIN_REGISTRY, e.g.:
         "sharepoint": "db_chat_ai.plugins.sharepoint:SharePointPlugin"
  3. Add its flag to PLUGINS in ai-conf.py: PLUGINS = {..., "sharepoint": True}
  4. If it needs its own config (a site URL, credentials, ...), read those
     from ai-conf.py the same way SQLPlugin reads config.db_url, or from
     environment variables — follow the existing pattern, don't hardcode.

No core file (chat_engine.py, config.py, the loader) needs to change for
any of this — that's the point of the plugin architecture.
"""

from ..interfaces.plugin import Plugin


class TemplatePlugin(Plugin):
    name = "template"  # match the key you use in PLUGINS in ai-conf.py

    def __init__(self, config):
        # Read whatever this plugin needs from `config` (an AIConfig) or
        # from its own env vars here. Do any expensive setup (connecting,
        # loading files, ...) now, once, at construction — not per-query.
        # If a required dependency is missing, raise here (ImportError or
        # RuntimeError) — the plugin loader catches it, logs a warning,
        # and skips this plugin without crashing the app.
        pass

    @property
    def kind(self) -> str:
        # "sql" if this plugin exposes queryable structured data, or
        # "document" if it exposes free-text content to be searched.
        return "document"

    def describe(self) -> str:
        # Return a SMALL text summary for the planning prompt: a schema
        # (sql-kind) or a list of titles (document-kind). Never dump full
        # content here — this goes straight into every planning call.
        return ""

    def search(self, query: str):
        # sql-kind: query is a validated SQL string, return list[dict] rows.
        # document-kind: query is free text, return list[Chunk]-like objects
        # (see sources/documents.py's Chunk for the expected shape:
        # source, title, text).
        return []
