"""factories/reranker_factory.py — resolves FEATURES["reranker"] into a
concrete Reranker. Disabled (the default) costs nothing: NoReranker just
returns chunks unchanged."""

from ..interfaces.reranker import FutureCrossEncoderReranker, NoReranker, Reranker


class RerankerFactory:
    @staticmethod
    def create(config) -> Reranker:
        if not config.features.get("reranker", False):
            return NoReranker()

        reranker_type = config.reranker_type
        if reranker_type == "cross_encoder":
            return FutureCrossEncoderReranker()
        return NoReranker()
