"""Seed demo dispute data into SQLite for development / testing."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow imports from src/ when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from card_issues.sqlite_store import Dispute, Session, _engine, init_db

_DISPUTES = [
    # merchant_id, date, reason_code, resolution, amount, currency
    ("MER001", "2025-09-01", "10.4", "chargeback", 120.00, "USD"),
    ("MER001", "2025-09-15", "13.1", "merchant_won", 45.50, "USD"),
    ("MER001", "2025-10-02", "10.4", "chargeback", 200.00, "USD"),
    ("MER001", "2025-10-20", "12.6", "reversed", 89.99, "USD"),
    ("MER001", "2025-11-03", "10.4", "chargeback", 310.00, "USD"),
    ("MER001", "2025-11-18", "13.1", "merchant_won", 55.00, "USD"),
    ("MER001", "2025-12-05", "10.5", "chargeback", 77.00, "USD"),
    ("MER001", "2026-01-10", "13.2", "reversed", 140.00, "USD"),
    ("MER001", "2026-01-25", "10.4", "chargeback", 95.00, "USD"),
    ("MER001", "2026-02-14", "12.5", "merchant_won", 210.00, "USD"),
    ("MER001", "2026-03-01", "10.4", "chargeback", 330.00, "USD"),
    ("MER002", "2025-10-10", "10.4", "merchant_won", 500.00, "USD"),
    ("MER002", "2025-11-22", "13.1", "merchant_won", 275.00, "USD"),
    ("MER002", "2026-01-05", "11.1", "chargeback", 60.00, "USD"),
    ("MER002", "2026-02-28", "13.2", "reversed", 180.00, "USD"),
    ("MER003", "2026-01-15", "10.4", "chargeback", 420.00, "EUR"),
    ("MER003", "2026-02-20", "12.6", "reversed", 99.50, "EUR"),
    ("MER003", "2026-03-10", "13.1", "merchant_won", 315.00, "EUR"),
]


def main() -> None:
    init_db()
    with Session(_engine) as session:
        # Wipe existing rows so seed is idempotent
        session.query(Dispute).delete()
        session.bulk_save_objects(
            [
                Dispute(
                    merchant_id=mid,
                    date=date,
                    reason_code=rc,
                    resolution=res,
                    amount=amt,
                    currency=cur,
                )
                for mid, date, rc, res, amt, cur in _DISPUTES
            ]
        )
        session.commit()
    print(f"Seeded {len(_DISPUTES)} dispute rows for merchants: MER001, MER002, MER003")


if __name__ == "__main__":
    main()
