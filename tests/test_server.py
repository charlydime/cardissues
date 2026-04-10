"""Unit tests for server.py tools: visa_rules_search, merchant_dispute_lookup, kb_fallback."""

from __future__ import annotations

from unittest.mock import patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hit(
    doc_id: str = "10.4",
    document: str = "Condition 10.4 – Fraud body text",
    metadata: dict | None = None,
    distance: float = 0.2,
) -> dict:
    if metadata is None:
        metadata = {"condition_id": doc_id, "condition_family": int(doc_id.split(".")[0])}
    return {"id": doc_id, "document": document, "metadata": metadata, "distance": distance}


# ---------------------------------------------------------------------------
# visa_rules_search
# ---------------------------------------------------------------------------


class TestVisaRulesSearch:
    def test_returns_list(self):
        from card_issues.server import visa_rules_search

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit()]
            result = visa_rules_search("card-present", "10.4", ["avs_match"])
        assert isinstance(result, list)

    def test_result_has_required_keys(self):
        from card_issues.server import visa_rules_search

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit()]
            result = visa_rules_search("card-present", "10.4", [])
        assert len(result) == 1
        row = result[0]
        for key in ("rule_id", "section", "summary", "reference"):
            assert key in row, f"Missing key: {key}"

    def test_summary_truncated_to_400_chars(self):
        from card_issues.server import visa_rules_search

        long_doc = "x" * 600
        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit(document=long_doc)]
            result = visa_rules_search("card-present", "10.4", [])
        assert len(result[0]["summary"]) <= 400

    def test_falls_back_to_unfiltered_when_filtered_empty(self):
        """If the where-filtered search returns nothing, an unfiltered call is made."""
        from card_issues.server import visa_rules_search

        with patch("card_issues.server.chroma_store") as mock_cs:
            # First call (filtered) returns empty; second call (unfiltered) returns a hit.
            mock_cs.search.side_effect = [[], [_make_hit()]]
            result = visa_rules_search("any", "10.4", [])
        assert len(result) == 1
        assert mock_cs.search.call_count == 2

    def test_non_numeric_prefix_skips_where_filter(self):
        """A reason_code without a numeric prefix should not set a where filter."""
        from card_issues.server import visa_rules_search

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit()]
            visa_rules_search("any", "MISC", [])
        # search must have been called without a where argument (or where=None)
        call_kwargs = mock_cs.search.call_args[1]
        assert call_kwargs.get("where") is None

    def test_reference_contains_condition_id(self):
        from card_issues.server import visa_rules_search

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit(doc_id="13.1")]
            result = visa_rules_search("any", "13.1", [])
        assert "13.1" in result[0]["reference"]


# ---------------------------------------------------------------------------
# merchant_dispute_lookup
# ---------------------------------------------------------------------------


class TestMerchantDisputeLookup:
    def test_delegates_to_sqlite_store(self):
        from card_issues.server import merchant_dispute_lookup

        expected = {"total_disputes": 5, "recent_disputes": [], "resolution_stats": {}}
        with patch("card_issues.server.sqlite_store") as mock_ss:
            mock_ss.get_merchant_disputes.return_value = expected
            result = merchant_dispute_lookup("M001")
        mock_ss.get_merchant_disputes.assert_called_once_with("M001")
        assert result == expected

    def test_returns_dict(self):
        from card_issues.server import merchant_dispute_lookup

        with patch("card_issues.server.sqlite_store") as mock_ss:
            mock_ss.get_merchant_disputes.return_value = {
                "total_disputes": 0,
                "recent_disputes": [],
                "resolution_stats": {},
            }
            result = merchant_dispute_lookup("X")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# kb_fallback
# ---------------------------------------------------------------------------


class TestKbFallback:
    def test_no_hits_returns_empty_with_manual_review(self):
        from card_issues.server import kb_fallback

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = []
            result = kb_fallback("unknown question")
        assert result["answer"] == ""
        assert result["confidence"] == 0.0
        assert result["manual_review"] is True

    def test_result_keys_present(self):
        from card_issues.server import kb_fallback

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit(distance=0.1)]
            result = kb_fallback("some question")
        for key in ("answer", "confidence", "manual_review"):
            assert key in result

    def test_high_confidence_hit_sets_manual_review_false(self):
        from card_issues.server import kb_fallback

        with patch("card_issues.server.chroma_store") as mock_cs:
            # distance=0.1 → confidence=0.9, which is >= 0.5
            mock_cs.search.return_value = [_make_hit(distance=0.1)]
            result = kb_fallback("fraud rules")
        assert result["manual_review"] is False
        assert result["confidence"] >= 0.5

    def test_low_confidence_hit_sets_manual_review_true(self):
        from card_issues.server import kb_fallback

        with patch("card_issues.server.chroma_store") as mock_cs:
            # distance=0.8 → confidence=0.2, which is < 0.5
            mock_cs.search.return_value = [_make_hit(distance=0.8)]
            result = kb_fallback("obscure question")
        assert result["manual_review"] is True

    def test_answer_empty_when_confidence_below_threshold(self):
        from card_issues.server import kb_fallback

        with patch("card_issues.server.chroma_store") as mock_cs:
            # distance=0.75 → confidence=0.25, which is < 0.3
            mock_cs.search.return_value = [_make_hit(distance=0.75)]
            result = kb_fallback("very obscure")
        assert result["answer"] == ""

    def test_answer_populated_when_confidence_above_threshold(self):
        from card_issues.server import kb_fallback

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit(distance=0.1, document="The answer text")]
            result = kb_fallback("fraud rules")
        assert "The answer text" in result["answer"]

    def test_answer_truncated_to_800_chars(self):
        from card_issues.server import kb_fallback

        long_doc = "y" * 1000
        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit(distance=0.1, document=long_doc)]
            result = kb_fallback("question")
        assert len(result["answer"]) <= 800

    def test_confidence_is_float(self):
        from card_issues.server import kb_fallback

        with patch("card_issues.server.chroma_store") as mock_cs:
            mock_cs.search.return_value = [_make_hit(distance=0.3)]
            result = kb_fallback("question")
        assert isinstance(result["confidence"], float)
