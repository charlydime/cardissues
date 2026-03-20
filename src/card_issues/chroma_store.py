from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

_COLLECTION_NAME = "visa_rules"
_DEFAULT_CHROMA_PATH = Path(__file__).parent.parent.parent / "data" / "chroma"


def _chroma_path() -> Path:
    raw = os.getenv("CHROMA_PATH", str(_DEFAULT_CHROMA_PATH))
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(_chroma_path()))
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    collection = get_collection()
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)


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
