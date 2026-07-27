"""
factories/retriever_factory.py — turns FEATURES["keyword_search"] /
FEATURES["embedding_search"] into a concrete Retriever, or None if
document retrieval is disabled entirely. The rest of the app never
constructs a retriever implementation directly.
"""

from ..interfaces.retriever import EmbeddingRetriever, HybridRetriever, KeywordRetriever, Retriever
from ..sources.documents import Chunk


class RetrieverFactory:
    @staticmethod
    def create(config, chunks: list[Chunk]) -> Retriever | None:
        keyword_on = bool(config.features.get("keyword_search", True))
        embedding_on = bool(config.features.get("embedding_search", False))

        if not keyword_on and not embedding_on:
            return None  # document retrieval disabled — costs nothing
        if embedding_on and keyword_on:
            return HybridRetriever(chunks, KeywordRetriever(chunks), EmbeddingRetriever(chunks))
        if embedding_on:
            return EmbeddingRetriever(chunks)
        return KeywordRetriever(chunks)
