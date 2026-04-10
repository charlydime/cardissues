from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

_COLLECTION_NAME = "visa_rules"
_DEFAULT_CHROMA_PATH = Path(__file__).parent.parent.parent / "data" / "chroma"
_INGEST_META_FILE = ".last_ingest"


def _chroma_path() -> Path:
    raw = os.getenv("CHROMA_PATH", str(_DEFAULT_CHROMA_PATH))
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _meta_file() -> Path:
    return _chroma_path() / _INGEST_META_FILE


def _client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(_chroma_path()))


def get_collection() -> chromadb.Collection:
    return _client().get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def get_collection_info() -> dict:
    """Return chunk count and last-ingest ISO timestamp (or None if not yet ingested)."""
    collection = get_collection()
    count = collection.count()
    last_ingest: str | None = None
    meta_path = _meta_file()
    if meta_path.exists():
        try:
            last_ingest = json.loads(meta_path.read_text())["last_ingest"]
        except (KeyError, ValueError, json.JSONDecodeError):
            pass
    return {"count": count, "last_ingest": last_ingest}


def delete_collection() -> None:
    """Drop the ChromaDB collection and remove the ingest metadata file."""
    client = _client()
    try:
        client.delete_collection(name=_COLLECTION_NAME)
    except ValueError:
        pass  # collection did not exist
    meta_path = _meta_file()
    if meta_path.exists():
        meta_path.unlink()


def upsert_chunks(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    collection = get_collection()
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    _meta_file().write_text(
        json.dumps({"last_ingest": datetime.datetime.now(datetime.UTC).isoformat()})
    )


def search(
    query: str,
    n_results: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """Return ranked results as plain dicts with keys: id, document, metadata, distance."""
    collection = get_collection()
    kwargs: dict = {"query_texts": [query], "n_results": min(n_results, collection.count() or 1)}
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)

    rows = []
    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]
    for rid, doc, meta, dist in zip(ids, docs, metas, distances):
        rows.append({"id": rid, "document": doc, "metadata": meta, "distance": dist})
    return rows
