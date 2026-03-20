from __future__ import annotations

from fastmcp import FastMCP

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
    return [{"message": "Message received"}]


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
    return {"message": "Message received"}


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
    return {"message": "Message received"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
