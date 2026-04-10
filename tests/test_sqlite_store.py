"""Unit tests for sqlite_store: execute_readonly and get_merchant_disputes."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    """Create a fresh SQLite DB in a temp directory and wire it into sqlite_store."""
    db_file = tmp_path / "test_merchant.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    # Re-import so the module picks up the patched env var and creates a fresh engine.
    import importlib

    import card_issues.sqlite_store as store

    importlib.reload(store)

    # Create tables and return the module reference.
    store.init_db()
    return store


@pytest.fixture()
def db_with_data(tmp_db):
    """Seed a few dispute rows so queries have something to return."""
    engine = create_engine(f"sqlite:///{os.environ['DB_PATH']}")
    from sqlalchemy import text

    rows = [
        ("M001", "2025-01-10", "10.4", "chargeback", 150.0, "USD"),
        ("M001", "2025-02-20", "13.1", "merchant_won", 75.5, "USD"),
        ("M001", "2025-03-05", "10.4", "reversed", 200.0, "USD"),
        ("M002", "2025-04-01", "12.6", "chargeback", 50.0, "EUR"),
    ]
    with engine.begin() as conn:
        for merchant_id, date, reason_code, resolution, amount, currency in rows:
            conn.execute(
                text(
                    "INSERT INTO disputes "
                    "(merchant_id, date, reason_code, resolution, amount, currency) "
                    "VALUES (:mid, :date, :rc, :res, :amt, :cur)"
                ),
                {
                    "mid": merchant_id,
                    "date": date,
                    "rc": reason_code,
                    "res": resolution,
                    "amt": amount,
                    "cur": currency,
                },
            )
    return tmp_db


# ---------------------------------------------------------------------------
# execute_readonly
# ---------------------------------------------------------------------------


class TestExecuteReadonly:
    def test_select_returns_rows(self, db_with_data):
        rows = db_with_data.execute_readonly("SELECT * FROM disputes WHERE merchant_id = 'M001'")
        assert len(rows) == 3

    def test_select_returns_dicts(self, db_with_data):
        rows = db_with_data.execute_readonly("SELECT merchant_id, amount FROM disputes LIMIT 1")
        assert isinstance(rows[0], dict)
        assert "merchant_id" in rows[0]
        assert "amount" in rows[0]

    def test_select_empty_result(self, tmp_db):
        rows = tmp_db.execute_readonly("SELECT * FROM disputes WHERE merchant_id = 'NOBODY'")
        assert rows == []

    @pytest.mark.parametrize(
        "bad_sql",
        [
            "INSERT INTO disputes (merchant_id) VALUES ('x')",
            "UPDATE disputes SET amount = 0",
            "DELETE FROM disputes",
            "DROP TABLE disputes",
            "  insert into disputes VALUES (1,'x','y','z','w',1.0,'USD')",
        ],
    )
    def test_non_select_raises(self, tmp_db, bad_sql):
        with pytest.raises(ValueError, match="Only SELECT"):
            tmp_db.execute_readonly(bad_sql)

    def test_select_case_insensitive_keyword(self, tmp_db):
        """Lowercase 'select' must still be accepted."""
        rows = tmp_db.execute_readonly("select * from disputes limit 0")
        assert rows == []


# ---------------------------------------------------------------------------
# get_merchant_disputes
# ---------------------------------------------------------------------------


class TestGetMerchantDisputes:
    def test_known_merchant_structure(self, db_with_data):
        result = db_with_data.get_merchant_disputes("M001")
        assert set(result.keys()) == {"total_disputes", "recent_disputes", "resolution_stats"}

    def test_known_merchant_total(self, db_with_data):
        result = db_with_data.get_merchant_disputes("M001")
        assert result["total_disputes"] == 3

    def test_known_merchant_resolution_stats(self, db_with_data):
        result = db_with_data.get_merchant_disputes("M001")
        stats = result["resolution_stats"]
        assert stats["chargeback"] == 1
        assert stats["merchant_won"] == 1
        assert stats["reversed"] == 1

    def test_known_merchant_recent_disputes_fields(self, db_with_data):
        result = db_with_data.get_merchant_disputes("M001")
        for dispute in result["recent_disputes"]:
            assert "date" in dispute
            assert "reason_code" in dispute
            assert "resolution" in dispute
            assert "amount" in dispute
            assert "currency" in dispute

    def test_recent_disputes_capped_at_ten(self, db_with_data):
        result = db_with_data.get_merchant_disputes("M001")
        assert len(result["recent_disputes"]) <= 10

    def test_unknown_merchant_returns_empty(self, db_with_data):
        result = db_with_data.get_merchant_disputes("UNKNOWN")
        assert result["total_disputes"] == 0
        assert result["recent_disputes"] == []
        assert result["resolution_stats"] == {}
