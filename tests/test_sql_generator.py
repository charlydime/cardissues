from __future__ import annotations

import pytest

from card_issues.sql_generator import _TEMPLATES, generate_sql_query


class TestTemplateRegistry:
    def test_templates_is_list_of_tuples(self) -> None:
        assert isinstance(_TEMPLATES, list)
        for entry in _TEMPLATES:
            assert len(entry) == 2, "each entry must be a (pattern, template) 2-tuple"

    def test_templates_not_empty(self) -> None:
        assert len(_TEMPLATES) > 0


class TestGenerateSqlQuery:
    # ------------------------------------------------------------------
    # Merchant filter
    # ------------------------------------------------------------------
    def test_disputes_for_merchant(self) -> None:
        result = generate_sql_query("disputes for merchant M123")
        assert result["matched"] is True
        assert "merchant_id" in result["sql"]
        assert result["params"]["merchant_id"] == "M123"

    def test_disputes_by_merchant(self) -> None:
        result = generate_sql_query("disputes by merchant ACME_42")
        assert result["matched"] is True
        assert result["params"]["merchant_id"] == "ACME_42"

    # ------------------------------------------------------------------
    # Reason-code filter
    # ------------------------------------------------------------------
    def test_disputes_by_reason_code(self) -> None:
        result = generate_sql_query("disputes with reason code 10.4")
        assert result["matched"] is True
        assert "reason_code" in result["sql"]
        assert result["params"]["reason_code"] == "10.4"

    def test_disputes_for_reason_code(self) -> None:
        result = generate_sql_query("disputes for reason code 13.1")
        assert result["matched"] is True
        assert result["params"]["reason_code"] == "13.1"

    # ------------------------------------------------------------------
    # Date-range filter
    # ------------------------------------------------------------------
    def test_disputes_between_dates(self) -> None:
        result = generate_sql_query("disputes between 2025-01-01 and 2025-03-31")
        assert result["matched"] is True
        assert "BETWEEN" in result["sql"]
        assert result["params"]["start_date"] == "2025-01-01"
        assert result["params"]["end_date"] == "2025-03-31"

    def test_disputes_from_to_dates(self) -> None:
        result = generate_sql_query("disputes from 2025-06-01 to 2025-12-31")
        assert result["matched"] is True
        assert result["params"]["start_date"] == "2025-06-01"
        assert result["params"]["end_date"] == "2025-12-31"

    def test_disputes_since_date(self) -> None:
        result = generate_sql_query("disputes since 2025-04-01")
        assert result["matched"] is True
        assert ">=" in result["sql"]
        assert result["params"]["start_date"] == "2025-04-01"

    def test_disputes_before_date(self) -> None:
        result = generate_sql_query("disputes before 2025-07-01")
        assert result["matched"] is True
        assert result["params"]["end_date"] == "2025-07-01"

    # ------------------------------------------------------------------
    # Resolution filter
    # ------------------------------------------------------------------
    def test_disputes_by_resolution(self) -> None:
        result = generate_sql_query("disputes with resolution merchant_won")
        assert result["matched"] is True
        assert "resolution" in result["sql"]
        assert result["params"]["resolution"] == "merchant_won"

    # ------------------------------------------------------------------
    # Aggregate / analytics patterns
    # ------------------------------------------------------------------
    def test_count_disputes_by_reason(self) -> None:
        result = generate_sql_query("count of disputes by reason")
        assert result["matched"] is True
        assert "GROUP BY reason_code" in result["sql"]
        assert result["params"] == {}

    def test_total_disputes_per_merchant(self) -> None:
        result = generate_sql_query("total disputes per merchant")
        assert result["matched"] is True
        assert "GROUP BY merchant_id" in result["sql"]

    # ------------------------------------------------------------------
    # Amount filters
    # ------------------------------------------------------------------
    def test_disputes_above_amount(self) -> None:
        result = generate_sql_query("disputes above 500")
        assert result["matched"] is True
        assert ">" in result["sql"]
        assert float(result["params"]["amount"]) == 500.0  # type: ignore[arg-type]

    def test_disputes_below_amount(self) -> None:
        result = generate_sql_query("disputes below 100.50")
        assert result["matched"] is True
        assert float(result["params"]["amount"]) == 100.5  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Catch-all / list all
    # ------------------------------------------------------------------
    def test_list_all_disputes(self) -> None:
        result = generate_sql_query("list all disputes")
        assert result["matched"] is True
        assert result["params"] == {}

    def test_show_disputes(self) -> None:
        result = generate_sql_query("show disputes")
        assert result["matched"] is True

    # ------------------------------------------------------------------
    # Unrecognised question
    # ------------------------------------------------------------------
    def test_unrecognised_question_returns_not_matched(self) -> None:
        result = generate_sql_query("what is the weather today?")
        assert result["matched"] is False
        assert result["sql"] == ""
        assert result["params"] == {}

    # ------------------------------------------------------------------
    # SQL safety – output must always be a SELECT
    # ------------------------------------------------------------------
    @pytest.mark.parametrize(
        "question",
        [
            "disputes for merchant M1",
            "disputes with reason code 10.4",
            "disputes between 2025-01-01 and 2025-06-01",
            "list all disputes",
        ],
    )
    def test_output_is_select(self, question: str) -> None:
        result = generate_sql_query(question)
        if result["matched"]:
            assert result["sql"].strip().upper().startswith("SELECT")
