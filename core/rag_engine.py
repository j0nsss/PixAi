"""RAG engine: background scanner, chunker, BM25 retrieval."""

from __future__ import annotations
import logging
import os
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from config import (
    MATERI_DIR,
    SUPPORTED_EXTENSIONS,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K_CHUNKS,
    MAX_CONTEXT_CHARS,
    RESCAN_INTERVAL_SECONDS,
    SCHEDULE_FILE_PREFIXES,
    SCHEDULE_MAX_CHARS,
)

from core.file_parser import parse_file, ParseResult

logger = logging.getLogger(__name__)


# Stopwords for BM25 tokenization (English + Indonesian)
STOPWORDS = frozenset({
    # English
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "be", "this", "that", "it", "as", "by", "at",
    "from", "you", "your", "i", "we", "they", "he", "she", "it", "my",
    "our", "their", "his", "her", "its", "me", "us", "them", "what",
    "which", "who", "when", "where", "why", "how", "can", "could",
    "will", "would", "should", "may", "might", "must", "have", "has",
    "had", "do", "does", "did", "not", "no", "yes", "but", "if", "then",
    "else", "than", "so", "very", "just", "only", "also", "more", "most",
    "some", "any", "all", "each", "every", "other", "such", "own", "same",
    # Indonesian
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "adalah", "itu",
    "ini", "dengan", "atau", "apa", "bagaimana", "siapa", "kapan", "dimana",
    "saya", "aku", "tolong", "jelaskan", "adalah", "merupakan", "sebagai",
    "dalam", "akan", "sudah", "belum", "bisa", "bisa", "harus", "perlu",
    "tidak", "ada", "juga", "masih", "lebih", "kurang", "sangat", "cukup",
})


def tokenize(text: str) -> List[str]:
    """Tokenize text for BM25: lowercase, word chars, drop short + stopwords."""
    tokens = re.findall(r"\w+", text.lower())
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    if overlap >= size:
        raise ValueError("overlap must be less than size")

    text = text.strip()
    if not text:
        return []

    if len(text) <= size:
        return [text]

    chunks = []
    step = size - overlap
    start = 0

    while start < len(text):
        end = min(start + size, len(text))

        # If not the last chunk, try to snap to whitespace
        if end < len(text):
            # Look back up to 100 chars for whitespace
            search_start = max(end - 100, start)
            last_space = text.rfind(" ", search_start, end)
            if last_space != -1:
                end = last_space

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Next start with overlap
        next_start = end - overlap
        if next_start <= start:
            next_start = start + 1
        start = next_start

    return chunks


@dataclass
class ScanReport:
    """Report from a scan cycle."""

    files_total: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    chunks: int = 0
    warnings: List[str] = field(default_factory=list)
    folder_created: bool = False

    def status_text(self) -> str:
        """Human-readable status."""
        if self.folder_created:
            return "Created ./materi_kuliah. Add your notes and PDFs."
        if self.files_total == 0:
            return "materi_kuliah is empty. Answering from general knowledge."
        if self.files_indexed == 0:
            return f"Found {self.files_total} files but none had readable text (see log)."
        return f"Indexed {self.files_indexed} files · {self.chunks} chunks"


@dataclass
class IndexedFile:
    """Indexed file with chunk metadata."""

    rel_path: str
    mtime_ns: int
    size: int
    chunks: List[str]
    tokens: List[Counter]  # per-chunk token counts
    lengths: List[int]     # per-chunk lengths


@dataclass
class RetrievedChunk:
    """A retrieved chunk with score."""

    source: str
    chunk_index: int
    text: str
    score: float


class RagEngine:
    """RAG engine with incremental background scanning and BM25 retrieval."""

    def __init__(self, root: Path = MATERI_DIR) -> None:
        self._root = root
        self._lock = threading.Lock()
        self._files: dict[str, IndexedFile] = {}
        self._df: Counter = Counter()  # document frequency per token
        self._avgdl: float = 0.0
        self._n_chunks: int = 0
        self._stop = threading.Event()
        self._enabled = True
        self._last_report: Optional[ScanReport] = None

    def scan(self) -> ScanReport:
        """Scan the material directory and update index."""
        report = ScanReport()

        # Ensure folder exists
        if not self._root.exists():
            try:
                self._root.mkdir(parents=True, exist_ok=True)
                report.folder_created = True
                with self._lock:
                    self._files = {}
                    self._df = Counter()
                    self._avgdl = 0.0
                    self._n_chunks = 0
                    self._enabled = True
                return report
            except OSError as e:
                logger.error("Failed to create materi_kuliah folder: %s", e)
                self._enabled = False
                report.warnings.append(str(e))
                return report

        # Walk files
        seen: set[str] = set()
        new_files: dict[str, IndexedFile] = {}
        all_chunks: List[tuple[str, int, str, Counter, int]] = []  # (rel_path, chunk_idx, text, tokens, length)

        for dirpath, dirnames, filenames in os.walk(self._root, followlinks=False):
            # Skip hidden dirs and __pycache__
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]

            for fname in filenames:
                if fname.startswith(".") or fname.startswith("~$"):
                    continue

                ext = Path(fname).suffix.lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                report.files_total += 1
                rel_path = Path(dirpath).relative_to(self._root) / fname
                rel_str = str(rel_path).replace("\\", "/")
                seen.add(rel_str)

                full_path = self._root / rel_str

                # Check if unchanged
                try:
                    stat = full_path.stat()
                    mtime_ns = stat.st_mtime_ns
                    size = stat.st_size
                except OSError:
                    report.files_skipped += 1
                    report.warnings.append(f"cannot stat {rel_str}")
                    continue

                # Reuse existing if unchanged
                existing = self._files.get(rel_str)
                if existing and existing.mtime_ns == mtime_ns and existing.size == size:
                    new_files[rel_str] = existing
                    for i, (chunk, toks, length) in enumerate(zip(existing.chunks, existing.tokens, existing.lengths)):
                        all_chunks.append((rel_str, i, chunk, toks, length))
                    report.files_indexed += 1
                    continue

                # Parse and chunk
                result: ParseResult = parse_file(full_path)
                if not result.ok:
                    report.files_skipped += 1
                    report.warnings.extend(result.warnings)
                    continue

                chunks = chunk_text(result.text)
                if not chunks:
                    report.files_skipped += 1
                    report.warnings.append(f"{rel_str}: no chunks produced")
                    continue

                # Build token counters
                stem = Path(fname).stem
                chunk_tokens: List[Counter] = []
                chunk_lengths: List[int] = []
                for chunk in chunks:
                    toks = tokenize(stem + " " + chunk)
                    chunk_tokens.append(Counter(toks))
                    chunk_lengths.append(len(chunk))
                    for t in toks:
                        self._df[t] += 1

                indexed = IndexedFile(
                    rel_path=rel_str,
                    mtime_ns=mtime_ns,
                    size=size,
                    chunks=chunks,
                    tokens=chunk_tokens,
                    lengths=chunk_lengths,
                )
                new_files[rel_str] = indexed
                report.files_indexed += 1

                for i, (chunk, toks, length) in enumerate(zip(chunks, chunk_tokens, chunk_lengths)):
                    all_chunks.append((rel_str, i, chunk, toks, length))

        # Remove deleted files
        for old_path in set(self._files.keys()) - seen:
            old_file = self._files[old_path]
            for toks in old_file.tokens:
                for t, c in toks.items():
                    self._df[t] -= c
                    if self._df[t] <= 0:
                        del self._df[t]

        # Recompute stats
        self._n_chunks = len(all_chunks)
        if self._n_chunks > 0:
            total_len = sum(length for _, _, _, _, length in all_chunks)
            self._avgdl = total_len / self._n_chunks
        else:
            self._avgdl = 0.0

        # Swap atomically
        with self._lock:
            self._files = new_files

        report.chunks = self._n_chunks
        self._last_report = report
        return report

    def start_background_scan(self, on_update: Callable[[ScanReport], None]) -> None:
        """Start background scanning thread."""
        def _runner() -> None:
            # Initial scan
            report = self.scan()
            on_update(report)

            while not self._stop.wait(RESCAN_INTERVAL_SECONDS):
                report = self.scan()
                # Only call on_update if something changed
                if self._last_report and (
                    report.files_indexed != self._last_report.files_indexed
                    or report.chunks != self._last_report.chunks
                    or report.files_total != self._last_report.files_total
                ):
                    on_update(report)

        thread = threading.Thread(target=_runner, name="rag-scanner", daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop background scanning."""
        self._stop.set()

    def retrieve(self, query: str, top_k: int = TOP_K_CHUNKS) -> List[RetrievedChunk]:
        """BM25 retrieval."""
        with self._lock:
            if not self._enabled or self._n_chunks == 0:
                return []

            query_tokens = tokenize(query)
            if not query_tokens:
                return []

            N = self._n_chunks
            k1 = 1.5
            b = 0.75

            # Build list of (source, chunk_idx, text, score)
            scored: List[tuple[str, int, str, float]] = []

            for rel_path, indexed_file in self._files.items():
                for i, (chunk, toks, length) in enumerate(zip(indexed_file.chunks, indexed_file.tokens, indexed_file.lengths)):
                    score = 0.0
                    for term in query_tokens:
                        tf = toks.get(term, 0)
                        if tf == 0:
                            continue
                        df = self._df.get(term, 0)
                        if df == 0:
                            continue
                        import math
                        idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
                        denom = tf + k1 * (1 - b + b * length / self._avgdl)
                        score += idf * tf * (k1 + 1) / denom

                    if score > 0:
                        scored.append((rel_path, i, chunk, score))

            scored.sort(key=lambda x: x[3], reverse=True)
            return [
                RetrievedChunk(source=s, chunk_index=i, text=t, score=sc)
                for s, i, t, sc in scored[:top_k]
            ]

    def build_context(self, query: str, max_chars: int = MAX_CONTEXT_CHARS) -> tuple[str, List[str]]:
        """Build context string from retrieved chunks."""
        chunks = self.retrieve(query)
        if not chunks:
            return "", []

        parts = []
        sources = []
        total = 0

        for chunk in chunks:
            part = f"[Source: {chunk.source} · part {chunk.chunk_index + 1}]\n{chunk.text}"
            if total + len(part) > max_chars:
                if not parts:
                    # First chunk exceeds limit - hard truncate
                    part = part[:max_chars]
                    parts.append(part)
                    sources.append(chunk.source)
                break
            parts.append(part)
            total += len(part)
            if chunk.source not in sources:
                sources.append(chunk.source)

        context = "\n\n---\n\n".join(parts)
        return context, sources

    def get_schedule_context(self, max_chars: int = SCHEDULE_MAX_CHARS) -> str:
        """Get concatenated schedule file contents."""
        with self._lock:
            schedule_files = []
            for rel_path, indexed_file in self._files.items():
                stem = Path(rel_path).stem.lower()
                if any(stem.startswith(prefix) for prefix in SCHEDULE_FILE_PREFIXES):
                    schedule_files.append((rel_path, indexed_file))

            if not schedule_files:
                return ""

            parts = []
            total = 0
            for rel_path, indexed_file in schedule_files:
                for i, chunk in enumerate(indexed_file.chunks):
                    header = f"[{rel_path}]" if i == 0 else ""
                    part = f"{header}\n{chunk}" if header else chunk
                    if total + len(part) > max_chars:
                        if not parts:
                            part = part[:max_chars]
                            parts.append(part)
                        break
                    parts.append(part)
                    total += len(part)

            return "\n\n".join(parts)

    def stats(self) -> dict:
        """Get index statistics."""
        with self._lock:
            return {"files": len(self._files), "chunks": self._n_chunks}


if __name__ == "__main__":
    import argparse

    from utils.logger import setup_logging

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, help="Query to test retrieval")
    args = parser.parse_args()

    setup_logging(True)
    engine = RagEngine()
    report = engine.scan()
    print(report.status_text())
    for w in report.warnings:
        print(f"  WARNING: {w}")

    if args.query:
        context, sources = engine.build_context(args.query)
        print(f"\nSources: {sources}")
        print(f"Context (first 300 chars):\n{context[:300]}")