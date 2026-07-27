"""
documents.py — loads free-text content (.md, .txt files, and web pages)
and finds the paragraphs most relevant to a given question.

This is deliberately dependency-free (no vector DB, no embeddings API
call) so the library stays a "just pip install and go" package: relevance
is a simple keyword-overlap score over paragraph-sized chunks. That's
enough to pull the right handful of paragraphs into context for typical
FAQ / notes / documentation use — it is not a replacement for a real
vector search over huge document sets.
"""

import html.parser
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Chunk:
    source: str      # file path or URL this came from
    title: str       # filename or page title, for attribution in the prompt
    text: str


class _HTMLTextExtractor(html.parser.HTMLParser):
    """Minimal HTML -> plain text extraction (stdlib only). Good enough for
    typical FAQ/doc pages; not a full readability/boilerplate remover."""

    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.parts.append(data)

    def get_text(self) -> str:
        return "\n".join(p.strip() for p in self.parts if p.strip())

    def get_title(self) -> str:
        return " ".join(t.strip() for t in self.title_parts if t.strip())


def _split_into_chunks(text: str, source: str, title: str, chunk_chars: int) -> list[Chunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    buf = ""
    for para in paragraphs:
        if buf and len(buf) + len(para) + 2 > chunk_chars:
            chunks.append(Chunk(source=source, title=title, text=buf.strip()))
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf.strip():
        chunks.append(Chunk(source=source, title=title, text=buf.strip()))
    return chunks


def _expand_file_paths(paths: list[str]) -> list[str]:
    """Expands folders in the configured FILES list into individual
    .md/.txt files (csv files are handled separately by csv_tables.py)."""
    out: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if f.lower().endswith((".md", ".txt")):
                        out.append(os.path.join(root, f))
        elif p.lower().endswith((".md", ".txt")):
            out.append(p)
        # .csv entries are silently skipped here — csv_tables.py handles them.
    return out


def load_files(paths: list[str], chunk_chars: int = 1200) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in _expand_file_paths(paths):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        title = os.path.basename(path)
        chunks.extend(_split_into_chunks(text, source=path, title=title, chunk_chars=chunk_chars))
    return chunks


def load_web(urls: list[str], chunk_chars: int = 1200, timeout: int = 15) -> list[Chunk]:
    chunks: list[Chunk] = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "db-chat-ai/0.2"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode(errors="replace")
        except (urllib.error.URLError, TimeoutError, ValueError):
            continue

        extractor = _HTMLTextExtractor()
        extractor.feed(raw)
        text = extractor.get_text()
        title = extractor.get_title() or url
        chunks.extend(_split_into_chunks(text, source=url, title=title, chunk_chars=chunk_chars))
    return chunks


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def search(chunks: list[Chunk], query: str, top_k: int = 5) -> list[Chunk]:
    """Ranks chunks by simple keyword-overlap score against the query and
    returns the top_k. Ties broken by original order (stable sort)."""
    if not chunks or not query.strip():
        return []

    query_terms = set(_tokenize(query))
    if not query_terms:
        return chunks[:top_k]

    scored = []
    for chunk in chunks:
        chunk_terms = _tokenize(chunk.text) + _tokenize(chunk.title)
        if not chunk_terms:
            continue
        overlap = sum(1 for t in chunk_terms if t in query_terms)
        if overlap:
            scored.append((overlap, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [c for _score, c in scored[:top_k]]


def render_chunks_for_prompt(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no matching document content found)"
    parts = []
    for c in chunks:
        parts.append(f"--- from {c.title} ({c.source}) ---\n{c.text}")
    return "\n\n".join(parts)
