from __future__ import annotations

"""Ingest visa-guidelines.pdf into ChromaDB for visa_rules_search."""

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


def ingest(pdf_path: Path | None = None) -> None:
    path = pdf_path or _PDF_PATH
    if not path.exists():
        print(f"ERROR: PDF not found at {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {path} …")
    df = extract_conditions(path)
    print(f"Found {len(df)} conditions:\n{df['condition_id'].to_list()}")

    # Late import so the module is importable even without chromadb at parse time
    from card_issues.chroma_store import upsert_chunks  # noqa: PLC0415

    ids = df["condition_id"].to_list()
    documents = [
        f"Condition {row['condition_id']} – {row['title']}\n\n{row['body']}"
        for row in df.iter_rows(named=True)
    ]
    metadatas = [
        {
            "condition_id": row["condition_id"],
            "condition_family": int(row["condition_id"].split(".")[0]),
            "title": row["title"],
            "transaction_type": row["transaction_type"],
        }
        for row in df.iter_rows(named=True)
    ]

    upsert_chunks(ids, documents, metadatas)
    print(f"Upserted {len(ids)} chunks into ChromaDB.")


if __name__ == "__main__":
    ingest()
