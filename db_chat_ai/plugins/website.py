"""
plugins/website.py — the "website" plugin (WEB_URLS in ai-conf.py).

Loads web pages (unchanged logic in sources/documents.py: fetch, strip
HTML, chunk) and exposes them as a document-kind plugin, same as the
documents plugin.
"""

from ..interfaces.plugin import Plugin
from ..sources import documents as _documents


class WebsitePlugin(Plugin):
    name = "website"

    def __init__(self, config):
        self.urls = config.web_urls
        self.chunk_chars = config.doc_chunk_chars
        self.timeout = config.web_timeout
        self.chunks = _documents.load_web(self.urls, chunk_chars=self.chunk_chars, timeout=self.timeout) \
            if self.urls else []

    @property
    def kind(self) -> str:
        return "document"

    def describe(self) -> str:
        if not self.chunks:
            return ""
        titles = []
        for c in self.chunks:
            label = f"{c.title} ({c.source})"
            if label not in titles:
                titles.append(label)
        return "\n".join(f"  - {t}" for t in titles)

    def search(self, query: str, top_k: int = 5) -> list[_documents.Chunk]:
        return _documents.search(self.chunks, query, top_k=top_k)

    def refresh(self) -> None:
        self.chunks = _documents.load_web(self.urls, chunk_chars=self.chunk_chars, timeout=self.timeout) \
            if self.urls else []
