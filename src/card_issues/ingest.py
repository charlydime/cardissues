"""Ingest visa-guidelines.pdf into ChromaDB for visa_rules_search."""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

import pdfplumber
import polars as pl
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PDF_DEFAULT = Path(__file__).parent.parent.parent / "visa-guidelines.pdf"
_PDF_PATH = Path(os.getenv("PDF_PATH", str(_PDF_DEFAULT)))

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_CONDITION_HEADER = re.compile(r"Condition\s+(\d+\.\d+)\s*\n([^\n]+)")
_FOOTER = re.compile(
    r"Dispute Management Guidelines for Visa Merchants.*?\n"
    r"©.*?Reserved\.?",
    re.DOTALL,
)
_SECTION_BANNER = re.compile(r"^3 Dispute Conditions\s*\n", re.MULTILINE)

# Subsection headers are typically wh-questions or short imperative lines
# (e.g. "Why did I get this notification?", "How should I respond?",
# "What evidence should I provide?", "Important Information", "Time Limits").
# Pattern lengths: wh-question bodies are 3–79 chars (at least 3 to avoid false
# positives on very short phrases, at most 79 to stay within a single display line);
# "Important …" and "Time Limit …" suffixes are 2–60 chars.
_SUBSECTION_HEADER = re.compile(
    r"(?m)^("
    r"(?:Why|How|What|When|Who|Where)[^\n]{3,79}\?"
    r"|Important\s+[^\n]{2,60}"
    r"|Time\s+[Ll]imit[^\n]{0,60}"
    r")\s*$"
)


def _subsection_slug(header: str) -> str:
    """Convert a subsection header string into a short lowercase slug."""
    slug = header.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    # Truncate to 40 chars for readability; ChromaDB IDs have no hard limit
    # but short slugs keep collection introspection manageable.
    return slug.strip("_")[:40]


def split_into_subsections(
    condition_id: str,
    title: str,
    body: str,
) -> list[tuple[str, str, str]]:
    """Split a condition body by subsection headers.

    Returns a list of ``(chunk_id, subsection_name, document_text)`` tuples.
    When no subsection headers are found the whole body is returned as a single
    chunk whose ``chunk_id`` equals ``condition_id`` (preserving backwards
    compatibility with previously ingested data).
    """
    matches = list(_SUBSECTION_HEADER.finditer(body))

    if not matches:
        doc = f"Condition {condition_id} – {title}\n\n{body}"
        return [(condition_id, "full", doc)]

    chunks: list[tuple[str, str, str]] = []

    # Text that precedes the first subsection header
    preamble = body[: matches[0].start()].strip()
    if preamble:
        doc = f"Condition {condition_id} – {title}\n\n{preamble}"
        chunks.append((f"{condition_id}::preamble", "preamble", doc))

    for idx, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()

        slug = _subsection_slug(header)
        chunk_id = f"{condition_id}::{slug}"
        doc = f"Condition {condition_id} – {title}\n{header}\n\n{section_body}"
        chunks.append((chunk_id, header, doc))

    return chunks


def _infer_tx_type(title: str, body: str) -> str:
    text = (title + " " + body).lower()
    if "card-absent" in text or "card absent" in text or "card-not-present" in text:
        return "card-absent"
    if "card-present" in text or "card present" in text or "emv" in text:
        return "card-present"
    return "any"


def _clean(text: str) -> str:
    text = _FOOTER.sub("", text)
    text = _SECTION_BANNER.sub("", text)
    # collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_conditions(pdf_path: Path) -> pl.DataFrame:
    """Parse PDF and return a Polars DataFrame with one row per condition."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")

    full_text = "\n".join(pages)
    full_text = _clean(full_text)

    # Split on each "Condition X.Y" occurrence
    parts = _CONDITION_HEADER.split(full_text)
    # parts layout (after split with 2 capture groups):
    # [preamble, cond_id1, title1, body1, cond_id2, title2, body2, ...]

    rows: list[dict] = []
    # parts[0] is preamble before first condition
    i = 1
    while i + 2 < len(parts):
        condition_id = parts[i].strip()
        title = parts[i + 1].strip()
        body = _clean(parts[i + 2])
        tx_type = _infer_tx_type(title, body)
        rows.append(
            {
                "condition_id": condition_id,
                "title": title,
                "transaction_type": tx_type,
                "body": body,
            }
        )
        i += 3

    # Merge rows with the same condition_id (multi-page conditions)
    merged: dict[str, dict] = {}
    for row in rows:
        cid = row["condition_id"]
        if cid in merged:
            merged[cid]["body"] = merged[cid]["body"] + "\n\n" + row["body"]
        else:
            merged[cid] = dict(row)

    return pl.DataFrame(list(merged.values()))


def _print_index_state(pdf_path: Path) -> None:
    """Print the current ChromaDB index state compared to the PDF on disk."""
    from card_issues.chroma_store import get_collection_info  # noqa: PLC0415

    info = get_collection_info()
    print(f"Index state: {info['count']} chunks in ChromaDB collection.")
    if info["last_ingest"]:
        print(f"  Last ingested : {info['last_ingest']}")
    else:
        print("  Last ingested : (never)")
    if pdf_path.exists():
        mtime = datetime.datetime.fromtimestamp(
            pdf_path.stat().st_mtime, tz=datetime.UTC
        ).isoformat()
        print(f"  PDF last modified: {mtime}")
    else:
        print(f"  PDF last modified: (not found at {pdf_path})")


def ingest(pdf_path: Path | None = None, force: bool = False) -> None:
    path = pdf_path or _PDF_PATH
    _print_index_state(path)

    if not path.exists():
        print(f"ERROR: PDF not found at {path}", file=sys.stderr)
        sys.exit(1)

    if force:
        from card_issues.chroma_store import delete_collection  # noqa: PLC0415

        print("--force: dropping existing ChromaDB collection …")
        delete_collection()
        print("Collection dropped. Rebuilding from scratch …")

    print(f"Parsing {path} …")
    df = extract_conditions(path)
    print(f"Found {len(df)} conditions:\n{df['condition_id'].to_list()}")

    # Late import so the module is importable even without chromadb at parse time
    from card_issues.chroma_store import upsert_chunks  # noqa: PLC0415

    # Use a dict keyed by chunk_id to deduplicate; later entries win so that
    # merged multi-page bodies overwrite earlier partial ones.
    chunks_by_id: dict[str, tuple[str, dict]] = {}

    for row in df.iter_rows(named=True):
        chunks = split_into_subsections(row["condition_id"], row["title"], row["body"])
        base_meta = {
            "condition_id": row["condition_id"],
            "condition_family": int(row["condition_id"].split(".")[0]),
            "title": row["title"],
            "transaction_type": row["transaction_type"],
        }
        for chunk_id, subsection, document in chunks:
            chunks_by_id[chunk_id] = (document, {**base_meta, "subsection": subsection})

    all_ids = list(chunks_by_id.keys())
    all_documents = [v[0] for v in chunks_by_id.values()]
    all_metadatas = [v[1] for v in chunks_by_id.values()]

    upsert_chunks(all_ids, all_documents, all_metadatas)
    print(f"Upserted {len(all_ids)} chunks into ChromaDB.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest visa-guidelines.pdf into ChromaDB.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and rebuild the ChromaDB collection from scratch.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to the PDF file (defaults to $PDF_PATH or data/visa-guidelines.pdf).",
    )
    args = parser.parse_args()
    ingest(pdf_path=args.pdf, force=args.force)
