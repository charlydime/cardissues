from __future__ import annotations

import pytest

from card_issues import sqlite_store


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Point the engine at a fresh in-memory SQLite database for each test."""
    from sqlalchemy import create_engine

    from card_issues.sqlite_store import _Base

    engine = create_engine("sqlite:///:memory:", echo=False)
    _Base.metadata.create_all(engine)
    monkeypatch.setattr(sqlite_store, "_engine", engine)
    yield


# ---------------------------------------------------------------------------
# execute_readonly – SQL-injection guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stmt",
    [
        "DROP TABLE disputes",
        "INSERT INTO disputes VALUES (1, 'M1', '2025-01-01', 'RC1', 'chargeback', 100.0, 'USD')",
        "UPDATE disputes SET amount = 0",
        "DELETE FROM disputes WHERE 1=1",
    ],
)
def test_execute_readonly_rejects_non_select(stmt: str) -> None:
    with pytest.raises(ValueError, match="Only SELECT"):
        sqlite_store.execute_readonly(stmt)


def test_execute_readonly_allows_select() -> None:
    rows = sqlite_store.execute_readonly("SELECT 1 AS n")
    assert rows == [{"n": 1}]


# ---------------------------------------------------------------------------
# get_merchant_disputes – input validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_id",
    [
        "",                   # empty string
        "merchant 1",         # space
        "merchant;drop",      # semicolon
        "mid'1",              # single quote
        "mid\x00null",        # null byte
        "mid/path",           # slash
    ],
)
def test_get_merchant_disputes_rejects_invalid_id(bad_id: str) -> None:
    with pytest.raises(ValueError):
        sqlite_store.get_merchant_disputes(bad_id)


# ---------------------------------------------------------------------------
# get_merchant_disputes – not-found handling
# ---------------------------------------------------------------------------

def test_get_merchant_disputes_returns_not_found_for_unknown_merchant() -> None:
    result = sqlite_store.get_merchant_disputes("UNKNOWN123")
    assert result["found"] is False
    assert result["total_disputes"] == 0
    assert result["recent_disputes"] == []
    assert result["resolution_stats"] == {}


# ---------------------------------------------------------------------------
# get_merchant_disputes – happy path
# ---------------------------------------------------------------------------

def _insert_dispute(merchant_id: str, resolution: str = "chargeback") -> None:
    from sqlalchemy.orm import Session

    from card_issues.sqlite_store import Dispute

    with Session(sqlite_store._engine) as session:
        session.add(
            Dispute(
                merchant_id=merchant_id,
                date="2025-06-15",
                reason_code="10.4",
                resolution=resolution,
                amount=99.99,
                currency="USD",
            )
        )
        session.commit()


def test_get_merchant_disputes_found() -> None:
    _insert_dispute("MERCH-001", resolution="merchant_won")
    _insert_dispute("MERCH-001", resolution="chargeback")

    result = sqlite_store.get_merchant_disputes("MERCH-001")

    assert result["found"] is True
    assert result["total_disputes"] == 2
    assert len(result["recent_disputes"]) == 2
    assert result["resolution_stats"]["merchant_won"] == 1
    assert result["resolution_stats"]["chargeback"] == 1
