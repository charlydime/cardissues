from __future__ import annotations

import os
from collections import defaultdict

from dotenv import load_dotenv
from sqlalchemy import Column, Float, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

load_dotenv()

_DB_PATH = os.getenv("DB_PATH", "data/merchant.db")
_engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)


class _Base(DeclarativeBase):
    pass


class Dispute(_Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False)  # ISO-8601 e.g. "2025-11-03"
    reason_code = Column(String, nullable=False)
    resolution = Column(String, nullable=False)  # merchant_won | chargeback | reversed
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="USD")


def init_db() -> None:
    """Create all tables if they don't exist."""
    _Base.metadata.create_all(_engine)


def execute_readonly(sql: str, params: dict | None = None) -> list[dict]:
    """Run a SELECT statement and return rows as dicts.

    Raises ValueError for any non-SELECT statement to prevent writes.
    """
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        raise ValueError("Only SELECT statements are allowed via execute_readonly.")

    with Session(_engine) as session:
        result = session.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


def get_merchant_disputes(merchant_id: str) -> dict:
    """Return aggregated dispute data for the given merchant.

    Returns:
        total_disputes (int), recent_disputes (list), resolution_stats (dict)
    """
    rows = execute_readonly(
        "SELECT date, reason_code, resolution, amount, currency "
        "FROM disputes WHERE merchant_id = :mid ORDER BY date DESC",
        {"mid": merchant_id},
    )

    resolution_stats: dict[str, int] = defaultdict(int)
    for row in rows:
        resolution_stats[row["resolution"]] += 1

    recent = [
        {
            "date": r["date"],
            "reason_code": r["reason_code"],
            "resolution": r["resolution"],
            "amount": r["amount"],
            "currency": r["currency"],
        }
        for r in rows[:10]
    ]

    return {
        "total_disputes": len(rows),
        "recent_disputes": recent,
        "resolution_stats": dict(resolution_stats),
    }
