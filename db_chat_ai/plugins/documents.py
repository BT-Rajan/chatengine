"""
plugins/documents.py — the "documents" plugin (.md / .txt files).

Loads local documents (unchanged logic in sources/documents.py) and
exposes them as a document-kind plugin. The chat engine normally searches
across every document-kind plugin's chunks together via a shared
Retriever (see chat_engine.py), rather than calling search() on this
plugin directly — search() is provided for interface completeness and
for anyone using this plugin standalone.
"""

from ..interfaces.plugin import Plugin
from ..sources import documents as _documents


class DocumentsPlugin(Plugin):
    name = "documents"

    def __init__(self, config):
        self.paths = config.files
        self.chunk_chars = config.doc_chunk_chars
        self.chunks = _documents.load_files(self.paths, chunk_chars=self.chunk_chars)

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
        self.chunks = _documents.load_files(self.paths, chunk_chars=self.chunk_chars)
