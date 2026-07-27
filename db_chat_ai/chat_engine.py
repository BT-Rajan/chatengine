"""
chat_engine.py — orchestrates the plan -> gather -> answer pipeline over
whatever plugins (sql, csv, documents, website, ...) are enabled in
ai-conf.py, plus the optional retriever / reranker / cache / memory
components.

This module never imports a specific plugin, retriever, cache, or memory
implementation directly — it only depends on the interfaces (Plugin,
Retriever, Reranker, Cache, Memory) and asks the factories/loader to
build the concrete instances that match config. That's the extension
point: new plugins or retrieval strategies plug in by registering with a
factory, never by editing this file.

Public API (DBChat.ask) is unchanged from the pre-refactor version aside
from one new optional `session_id` parameter for conversation memory —
existing callers that don't pass it see identical behavior.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from . import llm_client
from .config import AIConfig, load_ai_config
from .factories import CacheFactory, MemoryFactory, RerankerFactory, RetrieverFactory, load_plugins
from .interfaces.reranker import Reranker
from .interfaces.retriever import Retriever
from .sources import documents

_PLAN_SYSTEM_PROMPT_TEMPLATE = """You are a database/document assistant. A \
non-technical person is asking a question in plain English. Your ONLY job \
right now is to decide HOW to answer it — not to answer it yet.

Available structured data (query with SQL, MySQL/SQLite dialect):
{structured_schema}

Available documents (search these for relevant passages; you do not see \
their full content here, only titles):
{document_titles}

Output ONLY a JSON object, nothing else, with this shape:
{{
  "sql": "<a single read-only SELECT query, or null>",
  "sql_source": "{sql_source_options}",
  "doc_query": "<a short search query to find relevant document passages, or null>"
}}

Rules:
1. Set "sql" only if the question needs structured data that exists in the \
schema above, and set "sql" to null if there is no structured data \
available or the question doesn't need it.
2. The query must be a single SELECT (or WITH ... SELECT) statement. Never \
write INSERT/UPDATE/DELETE/DROP/ALTER or anything that changes data.
3. Match casually, not literally — names mentioned by the user may only be \
a partial/informal match to real values; use LIKE '%...%' rather than an \
exact match.
4. Always include a reasonable LIMIT unless the question clearly wants a \
count or aggregate.
5. Set "doc_query" only if documents are available above and the question \
could be answered (fully or partly) from prose/notes/web content — a short \
set of keywords is fine, it does not need to be a full sentence.
6. Both "sql" and "doc_query" can be set at once if the question needs both \
kinds of data; both can also be null if the question can't be answered from \
anything available."""

_ANSWER_SYSTEM_PROMPT_TEMPLATE = """{style_prompt}

You are answering a question using ONLY the data given below — never say \
"check yourself" or "look it up", you already have what's needed. If the \
data below doesn't actually cover the question, say plainly that it isn't \
available rather than guessing.

Question: {question}

{structured_section}
{document_section}"""


@dataclass
class ChatTurn:
    role: str  # "user" or "assistant"
    content: str


@dataclass
class ChatResponse:
    reply: str
    sql: str | None = None
    row_count: int | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    doc_query: str | None = None
    doc_sources: list[str] = field(default_factory=list)
    error: str | None = None
    from_cache: bool = False


class DBChat:
    """Main entry point. Usage:

        chat = DBChat()
        response = chat.ask("how many open orders does Acme have?")
        print(response.reply)

    Which plugins (sql / csv / documents / website / ...) and which
    optional features (embedding search, reranking, caching, conversation
    memory) are active is entirely controlled by ai-conf.py — this class
    adapts to whatever's turned on via dependency injection, never by
    checking source-specific flags itself.
    """

    def __init__(self, config: AIConfig | None = None):
        self.config = config or load_ai_config()

        self.plugins = load_plugins(self.config)
        self.sql_plugins = {p.name: p for p in self.plugins if p.kind == "sql"}
        self.doc_plugins = [p for p in self.plugins if p.kind == "document"]

        self.retriever: Retriever | None = RetrieverFactory.create(
            self.config, self._collect_document_chunks()
        )
        self.reranker: Reranker = RerankerFactory.create(self.config)
        self.cache = CacheFactory.create(self.config)
        self.memory = MemoryFactory.create(self.config)

        self._structured_schema_cache: tuple[str, list[str]] | None = None

    # ── setup / lifecycle ─────────────────────────────────────────────────

    def _collect_document_chunks(self) -> list[documents.Chunk]:
        chunks: list[documents.Chunk] = []
        for plugin in self.doc_plugins:
            chunks.extend(getattr(plugin, "chunks", []))
        return chunks

    def refresh_sources(self) -> None:
        """Re-reads files/web/DB schema for every loaded plugin. Call after
        files on disk change, ai-conf.py's FILES/WEB_URLS are edited, or
        the database schema changes at runtime."""
        for plugin in self.plugins:
            refresh = getattr(plugin, "refresh", None)
            if callable(refresh):
                refresh()
        self._structured_schema_cache = None
        self.retriever = RetrieverFactory.create(self.config, self._collect_document_chunks())

    def _structured_schema_text(self) -> tuple[str, list[str]]:
        if self._structured_schema_cache is not None:
            return self._structured_schema_cache

        sections = []
        sql_source_names = []
        for name, plugin in self.sql_plugins.items():
            described = plugin.describe()
            if described:
                sections.append(f"[{name.upper()}]\n{described}")
                sql_source_names.append(name)

        text_ = "\n".join(sections) if sections else "(no structured data sources configured)"
        self._structured_schema_cache = (text_, sql_source_names)
        return self._structured_schema_cache

    def _document_titles_text(self) -> str:
        titles = []
        for plugin in self.doc_plugins:
            described = plugin.describe()
            if described:
                titles.append(described)
        return "\n".join(titles) if titles else "(no documents configured)"

    def _history_messages(self, history: list[ChatTurn] | list[dict] | None) -> list[dict]:
        if not history:
            return []
        turns = history[-self.config.max_history_turns:]
        out = []
        for t in turns:
            role = t.role if isinstance(t, ChatTurn) else t.get("role", "user")
            content = t.content if isinstance(t, ChatTurn) else t.get("content", "")
            out.append({"role": "user" if role == "user" else "assistant", "content": content})
        return out

    def _llm(self, messages: list[dict]) -> str:
        return llm_client.chat_completion(
            messages,
            api_key=self.config.api_key,
            model=self.config.model,
            base_url=self.config.base_url,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
        )

    # ── caching ───────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(message: str, session_id: str | None) -> str:
        return f"{session_id or '_'}::{message.strip().lower()}"

    @staticmethod
    def _response_to_json(resp: "ChatResponse") -> str:
        return json.dumps(
            {
                "reply": resp.reply, "sql": resp.sql, "row_count": resp.row_count,
                "rows": resp.rows, "doc_query": resp.doc_query, "doc_sources": resp.doc_sources,
                "error": resp.error,
            },
            default=str,
        )

    @staticmethod
    def _response_from_json(raw: str) -> "ChatResponse":
        d = json.loads(raw)
        return ChatResponse(**d, from_cache=True)

    # ── main entry point ──────────────────────────────────────────────────

    def ask(
        self,
        message: str,
        history: list[ChatTurn] | list[dict] | None = None,
        session_id: str | None = None,
    ) -> ChatResponse:
        message = (message or "").strip()
        if not message:
            return ChatResponse(reply="Ask me something about the data.", error="empty_message")

        if not self.config.api_key:
            return ChatResponse(
                reply="No AI API key configured. Set DEEPSEEK_API_KEY in ai-conf.py.",
                error="no_api_key",
            )

        if not self.plugins:
            return ChatResponse(
                reply="No data sources are configured. Enable at least one plugin in PLUGINS in ai-conf.py.",
                error="no_sources",
            )

        caching_enabled = self.config.features.get("cache", False)
        cache_key = self._cache_key(message, session_id)
        if caching_enabled:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return self._response_from_json(cached)

        # merge explicit history with session memory, if configured
        effective_history = list(history) if history else []
        if not effective_history and session_id and self.config.features.get("conversation_memory", False):
            effective_history = self.memory.load(session_id)

        structured_schema, sql_source_names = self._structured_schema_text()
        document_titles = self._document_titles_text()

        # Step 1: plan.
        plan_prompt = _PLAN_SYSTEM_PROMPT_TEMPLATE.format(
            structured_schema=structured_schema,
            document_titles=document_titles,
            sql_source_options=" | ".join(sql_source_names) + " | null" if sql_source_names else "null",
        )
        try:
            raw_plan = self._llm(
                [{"role": "system", "content": plan_prompt}]
                + self._history_messages(effective_history)
                + [{"role": "user", "content": message}]
            )
        except llm_client.LLMError as e:
            return ChatResponse(reply=f"AI error: {e}", error="llm_error")

        plan = self._extract_json(raw_plan)
        sql = plan.get("sql") if sql_source_names else None
        sql_source = plan.get("sql_source")
        doc_query = plan.get("doc_query") if self.retriever is not None else None

        # Step 2: gather.
        rows: list[dict[str, Any]] = []
        executed_sql: str | None = None
        sql_error: str | None = None

        if sql:
            plugin = self.sql_plugins.get(sql_source) or next(iter(self.sql_plugins.values()), None)
            if plugin is not None:
                try:
                    rows = plugin.search(sql)
                    executed_sql = sql
                except Exception as e:
                    sql_error = str(e)

        doc_snippets: list[documents.Chunk] = []
        if doc_query and self.retriever is not None:
            try:
                doc_snippets = self.retriever.retrieve(doc_query, top_k=self.config.doc_top_k)
                doc_snippets = self.reranker.rerank(doc_query, doc_snippets)
            except NotImplementedError as e:
                return ChatResponse(reply=f"Retrieval error: {e}", error="retrieval_not_implemented")

        if sql_error and not doc_snippets:
            return ChatResponse(
                reply="That query didn't run cleanly — try rephrasing the question.",
                sql=sql,
                error=sql_error,
            )

        if not rows and not doc_snippets and not sql_error:
            return ChatResponse(
                reply="I couldn't find anything relevant to that in the configured data.",
                error="no_results",
            )

        # Step 3: answer, in the configured style.
        structured_section = (
            f"Query results (as JSON):\n{json.dumps(rows, default=str)[:8000]}"
            if rows
            else ("(structured query failed, ignore)" if sql_error else "")
        )
        document_section = (
            f"Relevant document passages:\n{documents.render_chunks_for_prompt(doc_snippets)}"
            if doc_snippets
            else ""
        )

        answer_prompt = _ANSWER_SYSTEM_PROMPT_TEMPLATE.format(
            style_prompt=self.config.style_prompt,
            question=message,
            structured_section=structured_section,
            document_section=document_section,
        )
        try:
            reply = self._llm([{"role": "system", "content": answer_prompt}, {"role": "user", "content": message}])
        except llm_client.LLMError as e:
            return ChatResponse(reply=f"AI error: {e}", sql=executed_sql, rows=rows, error="llm_error")

        response = ChatResponse(
            reply=reply.strip(),
            sql=executed_sql,
            row_count=len(rows) if executed_sql else None,
            rows=rows,
            doc_query=doc_query,
            doc_sources=[c.source for c in doc_snippets],
        )

        if caching_enabled:
            self.cache.set(cache_key, self._response_to_json(response))

        if session_id and self.config.features.get("conversation_memory", False):
            self.memory.save(session_id, {"role": "user", "content": message})
            self.memory.save(session_id, {"role": "assistant", "content": response.reply})

        return response

    @staticmethod
    def _extract_json(raw: str) -> dict:
        text_ = raw.strip()
        if text_.startswith("```"):
            text_ = text_.strip("`")
            if text_.lower().startswith("json"):
                text_ = text_[4:]
        start, end = text_.find("{"), text_.rfind("}")
        if start == -1 or end == -1:
            return {}
        try:
            return json.loads(text_[start:end + 1])
        except json.JSONDecodeError:
            return {}
