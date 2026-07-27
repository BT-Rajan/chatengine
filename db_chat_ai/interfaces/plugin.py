"""
interfaces/plugin.py — base abstraction every data source implements.

A plugin is one of two kinds:

  "sql"      — has a schema and runs validated read-only SQL against it
               (the mysql/db plugin, the csv plugin).
  "document" — has a collection of free-text chunks that get searched by
               a Retriever (the documents plugin, the website plugin).

The chat engine only ever talks to plugins through this interface plus
the `kind` property — it never imports a specific plugin module, which is
what lets new plugins (sharepoint, github, confluence, ...) be added
later without touching core code, per the plugin loader in
factories/plugin_loader.py.
"""

from abc import ABC, abstractmethod
from typing import Any


class Plugin(ABC):
    #: short, stable identifier used in config (PLUGINS dict) and in the
    #: planner's "sql_source" field for sql-kind plugins.
    name: str = "plugin"

    @property
    @abstractmethod
    def kind(self) -> str:
        """'sql' or 'document'."""

    @abstractmethod
    def describe(self) -> str:
        """Text describing what this plugin can answer from — schema for
        sql-kind plugins, document titles for document-kind plugins. Fed
        into the planning prompt; must stay small, never full content."""

    @abstractmethod
    def search(self, query: str) -> Any:
        """sql-kind: query is a validated-by-caller SQL string, returns
        list[dict] rows. document-kind: query is free text, returns
        list[Chunk] (a convenience default; the chat engine normally
        searches across all document plugins' chunks together via a
        shared Retriever instead of calling this directly)."""

    def fetch(self, ref: str) -> Any:
        """Optional: fetch one specific item by reference (a table name,
        a file path, a URL). Default: unsupported."""
        raise NotImplementedError(f"{self.name} does not support fetch()")
