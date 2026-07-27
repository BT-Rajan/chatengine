"""
interfaces/reranker.py — optional re-scoring of retrieved document chunks
before they're shown to the answer step.

NoReranker (the default) passes chunks through unchanged, at zero cost.
FutureCrossEncoderReranker is a placeholder reserving the extension point
for a real ML reranker later — no ML model or library is imported here.
"""

from abc import ABC, abstractmethod

from ..sources.documents import Chunk


class Reranker(ABC):
    @abstractmethod
    def rerank(self, question: str, chunks: list[Chunk]) -> list[Chunk]:
        ...


class NoReranker(Reranker):
    """Default. Returns the chunks exactly as given."""

    def rerank(self, question: str, chunks: list[Chunk]) -> list[Chunk]:
        return chunks


class FutureCrossEncoderReranker(Reranker):
    """Placeholder for a future cross-encoder (or similar) reranker model.
    Intentionally unimplemented — enabling this without wiring a real model
    should fail loudly rather than silently behaving like NoReranker."""

    def rerank(self, question: str, chunks: list[Chunk]) -> list[Chunk]:
        raise NotImplementedError(
            "Cross-encoder reranking isn't implemented yet — this class is "
            "an extension point. Keep FEATURES['reranker'] = False (the "
            "default) until a real model is wired in here."
        )
