from __future__ import annotations

import re

import polars as pl

# ---------------------------------------------------------------------------
# Template registry
# Each entry is a (compiled_pattern, sql_template) tuple.
# Named groups in the pattern become :named bind-parameters in the template.
# ---------------------------------------------------------------------------

_TEMPLATES: list[tuple[re.Pattern[str], str]] = [
    # disputes for a specific merchant
    (
        re.compile(
            r"disputes?\s+(?:for|by|of)\s+merchant\s+(?P<merchant_id>\S+)",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE merchant_id = :merchant_id ORDER BY date DESC",
    ),
    # disputes by reason code
    (
        re.compile(
            r"disputes?\s+(?:with|for|by)\s+reason\s+code\s+(?P<reason_code>\S+)",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE reason_code = :reason_code ORDER BY date DESC",
    ),
    # disputes in a date range
    (
        re.compile(
            r"disputes?\s+(?:between|from)\s+(?P<start_date>\d{4}-\d{2}-\d{2})"
            r"\s+(?:and|to)\s+(?P<end_date>\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE date BETWEEN :start_date AND :end_date ORDER BY date DESC",
    ),
    # disputes on or after a date
    (
        re.compile(
            r"disputes?\s+(?:since|after|from)\s+(?P<start_date>\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE date >= :start_date ORDER BY date DESC",
    ),
    # disputes before a date
    (
        re.compile(
            r"disputes?\s+before\s+(?P<end_date>\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE date < :end_date ORDER BY date DESC",
    ),
    # disputes by resolution outcome
    (
        re.compile(
            r"disputes?\s+(?:with|by)\s+resolution\s+(?P<resolution>\S+)",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE resolution = :resolution ORDER BY date DESC",
    ),
    # count disputes by reason code (summary / analytics)
    (
        re.compile(
            r"(?:count|number|total)\s+(?:of\s+)?disputes?\s+by\s+reason",
            re.IGNORECASE,
        ),
        "SELECT reason_code, COUNT(*) AS dispute_count "
        "FROM disputes GROUP BY reason_code ORDER BY dispute_count DESC",
    ),
    # count disputes by merchant (summary / analytics)
    (
        re.compile(
            r"(?:count|number|total)\s+(?:of\s+)?disputes?\s+(?:per|by)\s+merchant",
            re.IGNORECASE,
        ),
        "SELECT merchant_id, COUNT(*) AS dispute_count "
        "FROM disputes GROUP BY merchant_id ORDER BY dispute_count DESC",
    ),
    # disputes above a currency amount
    (
        re.compile(
            r"disputes?\s+(?:above|over|greater\s+than)\s+(?P<amount>[\d.]+)",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE amount > :amount ORDER BY amount DESC",
    ),
    # disputes below a currency amount
    (
        re.compile(
            r"disputes?\s+(?:below|under|less\s+than)\s+(?P<amount>[\d.]+)",
            re.IGNORECASE,
        ),
        "SELECT * FROM disputes WHERE amount < :amount ORDER BY amount DESC",
    ),
    # all disputes (catch-all)
    (
        re.compile(r"(?:all|list|show)\s+disputes?", re.IGNORECASE),
        "SELECT * FROM disputes ORDER BY date DESC",
    ),
]


def _sanitise_params(raw: dict[str, str]) -> dict[str, str]:
    """Sanitise and normalise captured regex groups using Polars.

    Uses a single-row Polars DataFrame so that all transformations stay
    within the Polars ecosystem (requirement from AGENTS.md).

    Current transforms:
    - Strip leading/trailing whitespace from every value.
    - For columns whose name contains ``date``, coerce to ISO-8601
      (YYYY-MM-DD) and reject malformed values.
    - For columns whose name is ``amount``, coerce to a canonical float
      string representation and reject non-numeric values.
    """
    if not raw:
        return raw

    df = pl.DataFrame({k: [v] for k, v in raw.items()})

    # Trim whitespace on all string columns
    df = df.with_columns([pl.col(c).str.strip_chars() for c in df.columns])

    # Coerce date columns
    date_cols = [c for c in df.columns if "date" in c]
    for col in date_cols:
        try:
            df = df.with_columns(
                pl.col(col).str.to_date("%Y-%m-%d").dt.strftime("%Y-%m-%d").alias(col)
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid date value for '{col}': {df[col][0]!r}") from exc

    # Coerce amount columns
    amount_cols = [c for c in df.columns if c == "amount"]
    for col in amount_cols:
        try:
            df = df.with_columns(pl.col(col).cast(pl.Float64).cast(pl.String).alias(col))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid amount value: {df[col][0]!r}") from exc

    return {c: df[c][0] for c in df.columns}


def generate_sql_query(question: str) -> dict[str, object]:
    """Translate a natural-language *question* into a SQL query.

    Iterates over ``_TEMPLATES`` in order and returns the first match.

    Args:
        question: Plain-English question about disputes
                  (e.g. "disputes for merchant M123").

    Returns:
        A dict with:
        - ``sql`` (str): Parameterised SELECT statement.
        - ``params`` (dict[str, str]): Bind parameters extracted from the question.
        - ``matched`` (bool): ``True`` when a template matched, ``False`` otherwise.

    Raises:
        ValueError: Never — unrecognised questions return ``matched=False``.
    """
    for pattern, template in _TEMPLATES:
        m = pattern.search(question)
        if m:
            raw_params = {k: v for k, v in m.groupdict().items() if v is not None}
            params = _sanitise_params(raw_params)
            return {"sql": template, "params": params, "matched": True}

    return {"sql": "", "params": {}, "matched": False}
