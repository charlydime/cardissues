from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Point the module at a fresh in-memory / temp DB before importing sqlite_store
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DB_PATH"] = _tmp_db.name

from card_issues import sqlite_store  # noqa: E402 (import after env setup)


@pytest.fixture(autouse=True)
def _seed_db():
    """Create the disputes table and insert a few rows for each test."""
    sqlite_store.init_db()
    engine = create_engine(f"sqlite:///{_tmp_db.name}", echo=False)
    with Session(engine) as session:
        session.execute(text("DELETE FROM disputes"))
        cols = "merchant_id, date, reason_code, resolution, amount, currency"
        session.execute(
            text(f"INSERT INTO disputes ({cols}) VALUES (:mid, :dt, :rc, :res, :amt, :cur)"),
            [
                {
                    "mid": "M001",
                    "dt": "2024-03-01",
                    "rc": "10.4",
                    "res": "chargeback",
                    "amt": 120.0,
                    "cur": "USD",
                },
                {
                    "mid": "M001",
                    "dt": "2024-04-15",
                    "rc": "13.1",
                    "res": "merchant_won",
                    "amt": 45.50,
                    "cur": "USD",
                },
                {
                    "mid": "M002",
                    "dt": "2024-05-20",
                    "rc": "10.4",
                    "res": "reversed",
                    "amt": 300.0,
                    "cur": "USD",
                },
            ],
        )
        session.commit()
    yield


class TestExecuteReadonly:
    def test_select_returns_rows(self) -> None:
        rows = sqlite_store.execute_readonly("SELECT * FROM disputes")
        assert len(rows) == 3

    def test_select_with_where(self) -> None:
        rows = sqlite_store.execute_readonly(
            "SELECT * FROM disputes WHERE merchant_id = 'M001'"
        )
        assert len(rows) == 2
        assert all(r["merchant_id"] == "M001" for r in rows)

    def test_result_rows_are_dicts(self) -> None:
        rows = sqlite_store.execute_readonly("SELECT * FROM disputes LIMIT 1")
        assert isinstance(rows[0], dict)
        assert "merchant_id" in rows[0]

    def test_non_select_raises_value_error(self) -> None:
        cols = "merchant_id, date, reason_code, resolution, amount, currency"
        vals = "VALUES ('X', '2024-01-01', '1.1', 'chargeback', 1.0, 'USD')"
        with pytest.raises(ValueError, match="Only SELECT statements are allowed"):
            sqlite_store.execute_readonly(f"INSERT INTO disputes ({cols}) {vals}")

    def test_update_rejected(self) -> None:
        with pytest.raises(ValueError, match="Only SELECT statements are allowed"):
            sqlite_store.execute_readonly("UPDATE disputes SET amount = 0")

    def test_delete_rejected(self) -> None:
        with pytest.raises(ValueError, match="Only SELECT statements are allowed"):
            sqlite_store.execute_readonly("DELETE FROM disputes")

    def test_drop_rejected(self) -> None:
        with pytest.raises(ValueError, match="Only SELECT statements are allowed"):
            sqlite_store.execute_readonly("DROP TABLE disputes")

    def test_empty_result(self) -> None:
        rows = sqlite_store.execute_readonly(
            "SELECT * FROM disputes WHERE merchant_id = 'DOES_NOT_EXIST'"
        )
        assert rows == []
