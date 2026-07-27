"""factories/memory_factory.py — resolves FEATURES["conversation_memory"]
into a concrete Memory. Disabled (the default) costs nothing: NoMemory
allocates no storage."""

from ..interfaces.memory import InMemorySessionMemory, Memory, NoMemory


class MemoryFactory:
    @staticmethod
    def create(config) -> Memory:
        if not config.features.get("conversation_memory", False):
            return NoMemory()
        return InMemorySessionMemory(max_turns=config.memory_max_turns)
