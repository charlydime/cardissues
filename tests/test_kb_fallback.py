from __future__ import annotations

from unittest.mock import patch

import pytest

from card_issues.server import kb_fallback


def _make_hit(doc: str, distance: float, condition_id: str, title: str = "") -> dict:
    return {
        "id": condition_id,
        "document": doc,
        "metadata": {"condition_id": condition_id, "title": title},
        "distance": distance,
    }


class TestKbFallbackNoResults:
    def test_empty_collection_returns_defaults(self):
        with patch("card_issues.server.chroma_store.search", return_value=[]):
            result = kb_fallback("what is the time limit for disputes?")

        assert result == {"answer": "", "confidence": 0.0, "manual_review": True, "sources": []}


class TestKbFallbackLowConfidence:
    def test_low_confidence_returns_empty_answer_but_sources(self):
        hits = [_make_hit("Some policy text.", distance=0.85, condition_id="C1", title="Sec 1")]
        with patch("card_issues.server.chroma_store.search", return_value=hits):
            result = kb_fallback("obscure question")

        assert result["answer"] == ""
        assert result["confidence"] == pytest.approx(0.15, abs=1e-4)
        assert result["manual_review"] is True
        assert result["sources"] == ["C1"]


class TestKbFallbackHighConfidence:
    def test_single_hit_includes_section_title(self):
        hits = [
            _make_hit(
                "Cardholder must file within 120 days.",
                distance=0.1,
                condition_id="C2",
                title="Time Limits",
            )
        ]
        with patch("card_issues.server.chroma_store.search", return_value=hits):
            result = kb_fallback("what is the filing deadline?")

        assert result["confidence"] == pytest.approx(0.9, abs=1e-4)
        assert result["manual_review"] is False
        assert "[Time Limits]" in result["answer"]
        assert "Cardholder must file within 120 days." in result["answer"]
        assert result["sources"] == ["C2"]

    def test_multiple_hits_concatenated(self):
        hits = [
            _make_hit("First relevant text.", distance=0.1, condition_id="C3", title="Section A"),
            _make_hit("Second relevant text.", distance=0.2, condition_id="C4", title="Section B"),
            _make_hit("Third relevant text.", distance=0.3, condition_id="C5", title="Section C"),
        ]
        with patch("card_issues.server.chroma_store.search", return_value=hits):
            result = kb_fallback("general dispute procedure?")

        assert "First relevant text." in result["answer"]
        assert "Second relevant text." in result["answer"]
        assert "Third relevant text." in result["answer"]
        assert "[Section A]" in result["answer"]
        assert "[Section B]" in result["answer"]
        assert result["sources"] == ["C3", "C4", "C5"]

    def test_low_confidence_hits_excluded_from_answer(self):
        hits = [
            _make_hit("Good match text.", distance=0.1, condition_id="C6", title="Good"),
            _make_hit("Weak match text.", distance=0.8, condition_id="C7", title="Weak"),
        ]
        with patch("card_issues.server.chroma_store.search", return_value=hits):
            result = kb_fallback("dispute evidence requirements?")

        assert "Good match text." in result["answer"]
        assert "Weak match text." not in result["answer"]
        # Both IDs still appear in sources (all returned by the vector store)
        assert "C6" in result["sources"]
        assert "C7" in result["sources"]

    def test_hit_without_title_uses_plain_excerpt(self):
        hits = [
            _make_hit("Plain text without section.", distance=0.05, condition_id="C8", title="")
        ]
        with patch("card_issues.server.chroma_store.search", return_value=hits):
            result = kb_fallback("something?")

        assert result["answer"] == "Plain text without section."

    def test_moderate_confidence_triggers_manual_review(self):
        # distance=0.55 → confidence=0.45 which is ≥0.3 (answer present) but <0.5 (manual_review)
        hits = [_make_hit("Borderline text.", distance=0.55, condition_id="C9", title="Border")]
        with patch("card_issues.server.chroma_store.search", return_value=hits):
            result = kb_fallback("something borderline?")

        assert result["manual_review"] is True
        assert result["answer"] != ""

    def test_answer_excerpt_capped_at_400_chars_per_hit(self):
        long_doc = "X" * 600
        hits = [_make_hit(long_doc, distance=0.1, condition_id="C10", title="Long")]
        with patch("card_issues.server.chroma_store.search", return_value=hits):
            result = kb_fallback("long doc test?")

        # The section header "[Long]\n" + 400 chars from document
        assert len(result["answer"]) <= len("[Long]\n") + 400
