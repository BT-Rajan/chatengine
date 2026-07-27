"""
factories/plugin_loader.py — loads only the plugins enabled in
PLUGINS (ai-conf.py). This is the one place that knows every plugin's
module path, so adding a new plugin means adding one line here — nothing
else in the engine changes.

Disabled plugins are never imported, so a missing optional dependency for
a disabled plugin (e.g. no `pandas` installed and csv disabled) can never
break startup. If an ENABLED plugin fails to load (missing dependency,
bad config, unreachable service), that one plugin is skipped with a
warning rather than crashing the whole app — every other plugin still
works.
"""

import importlib
import warnings

PLUGIN_REGISTRY: dict[str, str] = {
    "sql": "db_chat_ai.plugins.mysql:SQLPlugin",
    "csv": "db_chat_ai.plugins.csv:CSVPlugin",
    "documents": "db_chat_ai.plugins.documents:DocumentsPlugin",
    "website": "db_chat_ai.plugins.website:WebsitePlugin",
    # New plugins register here — see plugins/_template.py for the pattern.
    # "sharepoint": "db_chat_ai.plugins.sharepoint:SharePointPlugin",
    # "github": "db_chat_ai.plugins.github:GitHubPlugin",
    # "confluence": "db_chat_ai.plugins.confluence:ConfluencePlugin",
}


def load_plugins(config) -> list:
    """Returns the list of successfully-constructed, enabled Plugin
    instances. `config` is an AIConfig (see config.py)."""
    plugins = []
    for plugin_name, enabled in config.plugins.items():
        if not enabled:
            continue

        target = PLUGIN_REGISTRY.get(plugin_name)
        if target is None:
            warnings.warn(f"db-chat-ai: no plugin registered for '{plugin_name}' — skipping.")
            continue

        module_path, class_name = target.split(":")
        try:
            module = importlib.import_module(module_path)
            plugin_cls = getattr(module, class_name)
            plugin = plugin_cls(config)
        except Exception as e:
            warnings.warn(
                f"db-chat-ai: plugin '{plugin_name}' is enabled but failed to load "
                f"({type(e).__name__}: {e}) — continuing without it."
            )
            continue

        # sql-kind plugins with nothing to query (e.g. csv enabled but no
        # .csv files present) contribute nothing — skip them quietly.
        if getattr(plugin, "is_active", True) is False:
            continue

        plugins.append(plugin)

    return plugins
