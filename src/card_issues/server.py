from __future__ import annotations

from fastmcp import FastMCP

from card_issues import chroma_store, sql_generator, sqlite_store

mcp = FastMCP(
    name="visa-guidelines",
    instructions="Read-only MCP server for Visa dispute guidelines. "
    "Use visa_rules_search to find applicable VISA rules for a case, "
    "merchant_dispute_lookup to retrieve a merchant's dispute history, "
    "and kb_fallback for free-text knowledge-base questions.",
)


@mcp.tool()
def visa_rules_search(
    transaction_type: str,
    reason_code: str,
    evidence_flags: list[str],
) -> list[dict]:
    """Find applicable VISA rule sections for a dispute case.

    Args:
        transaction_type: Type of transaction (e.g. "card-present", "card-not-present").
        reason_code: Visa dispute reason code (e.g. "10.4", "13.1").
        evidence_flags: List of evidence indicators present in the case
                        (e.g. ["signed_receipt", "avs_match"]).

    Returns:
        List of matching rule sections, each with fields:
        rule_id, section, summary, and reference.
    """
    query = f"{transaction_type} {reason_code} {' '.join(evidence_flags)}"

    # Optionally narrow by condition family derived from the reason_code prefix
    where: dict | None = None
    prefix = reason_code.split(".")[0]
    if prefix.isdigit():
        where = {"condition_family": {"$eq": int(prefix)}}

    hits = chroma_store.search(query, n_results=5, where=where)

    if not hits:
        # Fall back to unfiltered search
        hits = chroma_store.search(query, n_results=5)

    return [
        {
            "rule_id": h["metadata"].get("condition_id", h["id"]),
            "section": h["metadata"].get("title", ""),
            "summary": h["document"][:400],
            "reference": (
                f"Visa Dispute Management Guidelines – "
                f"Condition {h['metadata'].get('condition_id', h['id'])}"
            ),
        }
        for h in hits
    ]


@mcp.tool()
def merchant_dispute_lookup(merchant_id: str) -> dict:
    """Retrieve dispute history and statistics for a merchant.

    Args:
        merchant_id: Unique merchant identifier.

    Returns:
        Dictionary with:
        - total_disputes (int)
        - recent_disputes (list of dicts with date, reason_code, resolution)
        - resolution_stats (dict with counts per resolution outcome)
    """
    return sqlite_store.get_merchant_disputes(merchant_id)


@mcp.tool()
def kb_fallback(question: str) -> dict:
    """Answer a free-text question from the Visa dispute knowledge base.

    Use this tool when visa_rules_search and merchant_dispute_lookup do not
    fully address the query, or when the user asks a general policy question.

    Args:
        question: Plain-English question about Visa dispute rules or procedures.

    Returns:
        Dictionary with:
        - answer (str) — best-effort KB answer, or empty string when unknown
        - confidence (float) — match confidence score between 0.0 and 1.0
        - manual_review (bool) — True when confidence is too low for automation
    """
    hits = chroma_store.search(question, n_results=1)
    if not hits:
        return {"answer": "", "confidence": 0.0, "manual_review": True}

    top = hits[0]
    # Cosine distance in [0, 2]; with normalised vectors typically in [0, 1].
    # Convert to a confidence score in [0, 1].
    confidence = round(max(0.0, 1.0 - top["distance"]), 4)
    answer = top["document"][:800] if confidence >= 0.3 else ""
    manual_review = confidence < 0.5

    return {"answer": answer, "confidence": confidence, "manual_review": manual_review}


@mcp.tool()
def query_disputes(question: str) -> dict:
    """Translate a natural-language question into SQL and execute it against the disputes database.

    Use this tool when you need to query disputes with a specific filter
    (merchant, reason code, date range, amount, or resolution outcome).

    Args:
        question: Plain-English question about disputes
                  (e.g. "disputes for merchant M123",
                   "disputes between 2025-01-01 and 2025-03-31").

    Returns:
        Dictionary with:
        - sql (str) — parameterised SELECT statement, or empty string if no
          template matched.
        - params (dict) — bind parameters extracted from the question.
        - matched (bool) — False when the question was not recognised.
        - rows (list[dict]) — query results (only present when matched is True).
    """
    result = sql_generator.generate_sql_query(question)
    if not result["matched"]:
        return result

    rows = sqlite_store.execute_readonly(str(result["sql"]), dict(result["params"]))  # type: ignore[arg-type]
    return {**result, "rows": rows}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
