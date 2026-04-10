"""Unit tests for ingest helpers: _clean, _infer_tx_type, and extract_conditions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from card_issues.ingest import _clean, _infer_tx_type, extract_conditions

# ---------------------------------------------------------------------------
# _clean
# ---------------------------------------------------------------------------


class TestClean:
    def test_removes_footer(self):
        text = (
            "Some rule text.\n"
            "Dispute Management Guidelines for Visa Merchants some extra\n"
            "© 2024 Visa Inc. All Rights Reserved.\n"
            "More text."
        )
        result = _clean(text)
        assert "Dispute Management Guidelines" not in result
        assert "©" not in result
        assert "More text." in result

    def test_collapses_blank_lines(self):
        text = "Line 1\n\n\n\n\nLine 2"
        result = _clean(text)
        assert "\n\n\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_strips_whitespace(self):
        text = "  \n  hello  \n  "
        assert _clean(text) == "hello"

    def test_removes_section_banner(self):
        text = "3 Dispute Conditions\n\nFirst condition body."
        result = _clean(text)
        assert "3 Dispute Conditions" not in result
        assert "First condition body." in result

    def test_plain_text_unchanged(self):
        text = "No footers or banners here."
        assert _clean(text) == text


# ---------------------------------------------------------------------------
# _infer_tx_type
# ---------------------------------------------------------------------------


class TestInferTxType:
    @pytest.mark.parametrize(
        "title,body,expected",
        [
            ("Card-Not-Present Transaction", "Dispute details", "card-absent"),
            ("Fraud", "card absent transaction occurred", "card-absent"),
            ("Card-Absent Environment", "some body", "card-absent"),
            ("Card-Present EMV", "chip transaction", "card-present"),
            ("Counterfeit", "EMV chip used at terminal", "card-present"),
            ("General Rule", "No specific transaction type", "any"),
            ("", "", "any"),
        ],
    )
    def test_classification(self, title, body, expected):
        assert _infer_tx_type(title, body) == expected

    def test_card_absent_takes_priority_in_title(self):
        # "card-not-present" in title should yield card-absent
        assert _infer_tx_type("Card-Not-Present", "EMV chip") == "card-absent"


# ---------------------------------------------------------------------------
# extract_conditions
# ---------------------------------------------------------------------------


class TestExtractConditions:
    def _make_mock_pdf(self, pages: list[str]):
        """Return a mock pdfplumber PDF whose pages yield the given text strings."""
        mock_pages = []
        for text in pages:
            page = MagicMock()
            page.extract_text.return_value = text
            mock_pages.append(page)

        mock_pdf = MagicMock()
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdf.pages = mock_pages
        return mock_pdf

    def test_returns_polars_dataframe(self, tmp_path):
        pdf_text = (
            "Preamble text.\n"
            "Condition 10.4\n"
            "Fraud – Card-Not-Present\n"
            "A fraudulent card-not-present transaction was disputed.\n"
        )
        mock_pdf = self._make_mock_pdf([pdf_text])
        with patch("pdfplumber.open", return_value=mock_pdf):
            df = extract_conditions(Path("fake.pdf"))
        assert isinstance(df, pl.DataFrame)

    def test_correct_columns(self, tmp_path):
        pdf_text = "Condition 10.4\nFraud Title\nBody text here.\n"
        mock_pdf = self._make_mock_pdf([pdf_text])
        with patch("pdfplumber.open", return_value=mock_pdf):
            df = extract_conditions(Path("fake.pdf"))
        assert set(df.columns) == {"condition_id", "title", "transaction_type", "body"}

    def test_parses_multiple_conditions(self):
        pdf_text = (
            "Condition 10.4\nFirst Title\nFirst body.\nCondition 13.1\nSecond Title\nSecond body.\n"
        )
        mock_pdf = self._make_mock_pdf([pdf_text])
        with patch("pdfplumber.open", return_value=mock_pdf):
            df = extract_conditions(Path("fake.pdf"))
        assert len(df) == 2
        assert "10.4" in df["condition_id"].to_list()
        assert "13.1" in df["condition_id"].to_list()

    def test_merges_duplicate_condition_ids(self):
        """The same condition_id on two pages should be merged into one row."""
        page1 = "Condition 10.4\nFraud Title\nFirst part of body.\n"
        page2 = "Condition 10.4\nFraud Title\nSecond part of body.\n"
        mock_pdf = self._make_mock_pdf([page1, page2])
        with patch("pdfplumber.open", return_value=mock_pdf):
            df = extract_conditions(Path("fake.pdf"))
        assert len(df) == 1
        body = df.filter(pl.col("condition_id") == "10.4")["body"][0]
        assert "First part" in body
        assert "Second part" in body

    def test_transaction_type_inferred(self):
        pdf_text = "Condition 10.4\nCard-Not-Present Fraud\nTransaction disputed.\n"
        mock_pdf = self._make_mock_pdf([pdf_text])
        with patch("pdfplumber.open", return_value=mock_pdf):
            df = extract_conditions(Path("fake.pdf"))
        assert df["transaction_type"][0] == "card-absent"
