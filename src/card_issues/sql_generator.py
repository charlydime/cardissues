from __future__ import annotations

import re

# Each entry is (compiled_pattern, sql_template).
# Named groups in the pattern must match {placeholder} names in the template.
_TEMPLATES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"disputes?\s+for\s+merchant\s+['\"]?(?P<merchant_id>[A-Za-z0-9_\-]+)['\"]?",
            re.IGNORECASE,
        ),
        "SELECT id, date, reason_code, resolution, amount, currency "
        "FROM disputes WHERE merchant_id = '{merchant_id}' ORDER BY date DESC",
    ),
    (
        re.compile(
            r"disputes?\s+with\s+reason\s+code\s+['\"]?(?P<reason_code>[0-9]+\.[0-9]+)['\"]?",
            re.IGNORECASE,
        ),
        "SELECT id, merchant_id, date, resolution, amount, currency "
        "FROM disputes WHERE reason_code = '{reason_code}' ORDER BY date DESC",
    ),
    (
        re.compile(
            r"(?:total\s+)?disputes?\s+(?:count|number|how\s+many)\s+for\s+merchant\s+"
            r"['\"]?(?P<merchant_id>[A-Za-z0-9_\-]+)['\"]?",
            re.IGNORECASE,
        ),
        "SELECT COUNT(*) AS total_disputes FROM disputes WHERE merchant_id = '{merchant_id}'",
    ),
    (
        re.compile(
            r"['\"]?(?P<resolution>merchant_won|chargeback|reversed)['\"]?\s+disputes?",
            re.IGNORECASE,
        ),
        "SELECT id, merchant_id, date, reason_code, amount, currency "
        "FROM disputes WHERE resolution = '{resolution}' ORDER BY date DESC",
    ),
    (
        re.compile(
            r"disputes?\s+(?:after|since|from)\s+(?P<start_date>\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        "SELECT id, merchant_id, date, reason_code, resolution, amount, currency "
        "FROM disputes WHERE date >= '{start_date}' ORDER BY date DESC",
    ),
    (
        re.compile(
            r"disputes?\s+(?:before|until|up\s+to)\s+(?P<end_date>\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        "SELECT id, merchant_id, date, reason_code, resolution, amount, currency "
        "FROM disputes WHERE date <= '{end_date}' ORDER BY date DESC",
    ),
    (
        re.compile(
            r"disputes?\s+(?:greater|more|over|above)\s+than\s+\$?(?P<amount>[0-9]+(?:\.[0-9]+)?)",
            re.IGNORECASE,
        ),
        "SELECT id, merchant_id, date, reason_code, resolution, amount, currency "
        "FROM disputes WHERE amount > {amount} ORDER BY amount DESC",
    ),
    (
        re.compile(
            r"(?:all\s+)?disputes?(?:\s+records?)?",
            re.IGNORECASE,
        ),
        "SELECT id, merchant_id, date, reason_code, resolution, amount, currency "
        "FROM disputes ORDER BY date DESC LIMIT 100",
    ),
]


def generate_sql(question: str) -> str:
    """Translate a natural-language question into a SQL SELECT statement.

    Iterates over ``_TEMPLATES`` in order and returns the first match,
    substituting named groups into the template.  Raises ``ValueError``
    when no template matches the question.

    Args:
        question: Plain-English question about dispute data.

    Returns:
        A SQL SELECT statement string.

    Raises:
        ValueError: If no template matches the question.
    """
    for pattern, template in _TEMPLATES:
        m = pattern.search(question)
        if m:
            return template.format(**m.groupdict())
    raise ValueError(
        f"No SQL template matches the question: {question!r}. "
        "Please rephrase or add a new template to sql_generator._TEMPLATES."
    )
