"""
interfaces/retriever.py — how document chunks (from the documents/website
plugins) get searched for a question.

KeywordRetriever wraps the existing keyword-overlap search unchanged.
EmbeddingRetriever and HybridRetriever are placeholders that reserve the
extension point — no embedding library is imported at module level, so
having these classes defined costs nothing when embeddings are disabled
(the default). They only raise if something actually tries to use them.
"""

from abc import ABC, abstractmethod

from ..sources.documents import Chunk, search as keyword_search


class Retriever(ABC):
    """Given a question, return the most relevant chunks from whatever
    corpus this retriever was built with."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks

    @abstractmethod
    def retrieve(self, question: str, top_k: int = 5) -> list[Chunk]:
        ...


class KeywordRetriever(Retriever):
    """The only retriever actually implemented today — the same
    keyword-overlap ranking db-chat-ai has always used."""

    def retrieve(self, question: str, top_k: int = 5) -> list[Chunk]:
        return keyword_search(self.chunks, question, top_k=top_k)


class EmbeddingRetriever(Retriever):
    """Placeholder for future embedding-based semantic search. Not wired
    to any embedding model or vector store. Enabling `embedding_search`
    in FEATURES without implementing this will raise clearly at query
    time rather than silently falling back — that's a deliberate choice
    so a misconfiguration doesn't look like "no results found"."""

    def retrieve(self, question: str, top_k: int = 5) -> list[Chunk]:
        raise NotImplementedError(
            "Embedding-based retrieval isn't implemented yet — this class "
            "exists as an extension point. Wire an embedding model/vector "
            "store here when you're ready to build it, or keep "
            "FEATURES['embedding_search'] = False to use keyword search."
        )


class HybridRetriever(Retriever):
    """Placeholder that combines keyword + embedding retrieval. Delegates
    to a KeywordRetriever and an EmbeddingRetriever; will raise via the
    embedding side until EmbeddingRetriever is actually implemented."""

    def __init__(self, chunks: list[Chunk], keyword: KeywordRetriever, embedding: EmbeddingRetriever):
        super().__init__(chunks)
        self.keyword = keyword
        self.embedding = embedding

    def retrieve(self, question: str, top_k: int = 5) -> list[Chunk]:
        # Placeholder merge strategy: keyword results first, embedding
        # results appended, de-duplicated by (source, text). Replace with
        # real score fusion (e.g. reciprocal rank fusion) once
        # EmbeddingRetriever is implemented.
        keyword_results = self.keyword.retrieve(question, top_k=top_k)
        try:
            embedding_results = self.embedding.retrieve(question, top_k=top_k)
        except NotImplementedError:
            embedding_results = []

        seen = {(c.source, c.text) for c in keyword_results}
        merged = list(keyword_results)
        for c in embedding_results:
            key = (c.source, c.text)
            if key not in seen:
                merged.append(c)
                seen.add(key)
        return merged[:top_k]
