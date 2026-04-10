"""Unit tests for chroma_store: upsert_chunks and search."""

from __future__ import annotations

import importlib
import uuid

import chromadb
import pytest

# ---------------------------------------------------------------------------
# Fake embedding function (avoids downloading the real ONNX model)
# ---------------------------------------------------------------------------


class _FakeEmbedding(chromadb.EmbeddingFunction):
    """Returns trivial fixed-size vectors so tests run without internet access."""

    def __init__(self) -> None:
        pass

    def name(self) -> str:
        return "fake-embedding"

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        # Deterministic: hash the text into a stable 16-dim vector.
        vectors = []
        for text in input:
            seed = hash(text) & 0xFFFF
            vec = [float((seed >> i) & 1) for i in range(16)]
            if not any(vec):
                vec[0] = 1.0
            vectors.append(vec)
        return vectors


# ---------------------------------------------------------------------------
# Shared in-process client (EphemeralClient reuses memory across instances)
# ---------------------------------------------------------------------------

_CLIENT = chromadb.EphemeralClient()


def _fresh_collection() -> chromadb.Collection:
    """Return a brand-new, uniquely-named collection for test isolation."""
    return _CLIENT.get_or_create_collection(
        name=f"test_{uuid.uuid4().hex}",
        embedding_function=_FakeEmbedding(),
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def chroma_store(monkeypatch):
    """Provide chroma_store backed by a fresh isolated collection."""
    import card_issues.chroma_store as store

    importlib.reload(store)

    collection = _fresh_collection()
    monkeypatch.setattr(store, "get_collection", lambda: collection)
    return store


# ---------------------------------------------------------------------------
# upsert_chunks
# ---------------------------------------------------------------------------


class TestUpsertChunks:
    def test_upsert_single_chunk(self, chroma_store):
        chroma_store.upsert_chunks(
            ids=["rule-1"],
            documents=["Condition 10.4 – Fraud"],
            metadatas=[{"condition_id": "10.4", "condition_family": 10}],
        )
        collection = chroma_store.get_collection()
        assert collection.count() == 1

    def test_upsert_multiple_chunks(self, chroma_store):
        chroma_store.upsert_chunks(
            ids=["rule-1", "rule-2", "rule-3"],
            documents=["Doc A", "Doc B", "Doc C"],
            metadatas=[
                {"condition_id": "10.4", "condition_family": 10},
                {"condition_id": "13.1", "condition_family": 13},
                {"condition_id": "12.6", "condition_family": 12},
            ],
        )
        assert chroma_store.get_collection().count() == 3

    def test_upsert_is_idempotent(self, chroma_store):
        """Upserting the same id twice should not create duplicate documents."""
        meta = {"condition_id": "10.4", "condition_family": 10}
        chroma_store.upsert_chunks(["rule-1"], ["Original text"], [meta])
        chroma_store.upsert_chunks(["rule-1"], ["Updated text"], [meta])
        assert chroma_store.get_collection().count() == 1


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.fixture(autouse=True)
    def _seed(self, chroma_store):
        """Seed a small collection used by all search tests."""
        self.store = chroma_store
        chroma_store.upsert_chunks(
            ids=["fraud-absent", "fraud-present", "services"],
            documents=[
                "Condition 10.4 – card-not-present fraud dispute",
                "Condition 10.5 – card-present EMV chip counterfeit fraud",
                "Condition 13.1 – merchandise or services not received",
            ],
            metadatas=[
                {"condition_id": "10.4", "condition_family": 10, "transaction_type": "card-absent"},
                {
                    "condition_id": "10.5",
                    "condition_family": 10,
                    "transaction_type": "card-present",
                },
                {"condition_id": "13.1", "condition_family": 13, "transaction_type": "any"},
            ],
        )

    def test_search_returns_list(self):
        results = self.store.search("fraud")
        assert isinstance(results, list)

    def test_search_result_keys(self):
        results = self.store.search("fraud", n_results=1)
        assert len(results) >= 1
        row = results[0]
        assert "id" in row
        assert "document" in row
        assert "metadata" in row
        assert "distance" in row

    def test_search_n_results_respected(self):
        results = self.store.search("dispute", n_results=2)
        assert len(results) <= 2

    def test_search_distance_is_float(self):
        results = self.store.search("fraud", n_results=1)
        assert isinstance(results[0]["distance"], float)

    def test_search_with_where_filter(self):
        results = self.store.search(
            "fraud",
            n_results=3,
            where={"condition_family": {"$eq": 13}},
        )
        for r in results:
            assert r["metadata"]["condition_family"] == 13

    def test_search_empty_collection_returns_empty(self, monkeypatch):
        """search() on an empty collection should return []."""
        import card_issues.chroma_store as store

        importlib.reload(store)
        empty_collection = _fresh_collection()
        monkeypatch.setattr(store, "get_collection", lambda: empty_collection)
        results = store.search("anything")
        assert results == []
