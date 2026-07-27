"""
interfaces/memory.py — conversation memory infrastructure.

Deliberately unsophisticated: no summarization, no relevance ranking of
past turns, just "keep the last N messages for this session". Its only
job is to give the chat engine a session id -> get/save history hook so a
caller doesn't have to pass the full transcript back in on every request
if it doesn't want to. NoMemory (the default) makes this a complete no-op.
"""

from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Any


class Memory(ABC):
    @abstractmethod
    def load(self, session: str) -> list[dict[str, Any]]:
        """Returns the stored history for this session, oldest first."""

    @abstractmethod
    def save(self, session: str, message: dict[str, Any]) -> None:
        """Appends one message ({"role": ..., "content": ...}) to the
        session's history."""


class NoMemory(Memory):
    """Default. Conversation memory is opt-in — this makes the feature a
    true no-op (no storage allocated, nothing to configure) when disabled."""

    def load(self, session: str) -> list[dict[str, Any]]:
        return []

    def save(self, session: str, message: dict[str, Any]) -> None:
        return None


class InMemorySessionMemory(Memory):
    """Simple in-process, per-session ring buffer. Not persisted across
    restarts and not shared across processes — this is infrastructure for
    a single running app, not a durable store. Swap in a database- or
    Redis-backed Memory implementation for that; the interface is the
    same either way."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._sessions: dict[str, deque] = defaultdict(lambda: deque(maxlen=max_turns * 2))

    def load(self, session: str) -> list[dict[str, Any]]:
        return list(self._sessions[session])

    def save(self, session: str, message: dict[str, Any]) -> None:
        self._sessions[session].append(message)
