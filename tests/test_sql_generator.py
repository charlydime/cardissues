from __future__ import annotations

import pytest

from card_issues import sql_generator


class TestGenerateSql:
    def test_disputes_for_merchant(self) -> None:
        sql = sql_generator.generate_sql("disputes for merchant M123")
        assert "merchant_id = 'M123'" in sql
        assert sql.strip().upper().startswith("SELECT")

    def test_disputes_with_reason_code(self) -> None:
        sql = sql_generator.generate_sql("disputes with reason code 10.4")
        assert "reason_code = '10.4'" in sql
        assert sql.strip().upper().startswith("SELECT")

    def test_disputes_after_date(self) -> None:
        sql = sql_generator.generate_sql("disputes after 2024-01-01")
        assert "date >= '2024-01-01'" in sql
        assert sql.strip().upper().startswith("SELECT")

    def test_disputes_before_date(self) -> None:
        sql = sql_generator.generate_sql("disputes before 2024-12-31")
        assert "date <= '2024-12-31'" in sql
        assert sql.strip().upper().startswith("SELECT")

    def test_disputes_above_amount(self) -> None:
        sql = sql_generator.generate_sql("disputes greater than $500")
        assert "amount > 500" in sql
        assert sql.strip().upper().startswith("SELECT")

    def test_all_disputes_fallback(self) -> None:
        sql = sql_generator.generate_sql("all disputes")
        assert sql.strip().upper().startswith("SELECT")
        assert "FROM disputes" in sql

    def test_unmatched_question_raises(self) -> None:
        with pytest.raises(ValueError, match="No SQL template matches"):
            sql_generator.generate_sql("zzz completely unrecognised gibberish xyz 999")

    def test_returned_sql_is_always_select(self) -> None:
        sql = sql_generator.generate_sql("disputes for merchant ABC")
        assert sql.strip().upper().startswith("SELECT"), "generate_sql must always return SELECT"
