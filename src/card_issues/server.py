from __future__ import annotations

from fastmcp import FastMCP

from card_issues import chroma_store, sql_generator, sql_generator, sqlite_store

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
            "section": (
                f"{h['metadata'].get('title', '')} – {h['metadata']['subsection']}"
                if h["metadata"].get("subsection") not in (None, "full", "preamble")
                else h["metadata"].get("title", "")
            ),
            "subsection": h["metadata"].get("subsection", "full"),
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
        - answer (str) — best-effort KB answer combining the top matching
          sections, or empty string when no confident match is found.
          Each section is prefixed with its title for easy citation.
        - confidence (float) — match confidence score between 0.0 and 1.0
          derived from the top result's cosine similarity.
        - manual_review (bool) — True when confidence is too low for automation
        - sources (list[str]) — condition IDs of the matched KB entries,
          ordered by relevance.
    """
    hits = chroma_store.search(question, n_results=3)
    if not hits:
        return {"answer": "", "confidence": 0.0, "manual_review": True, "sources": []}

    top = hits[0]
    # Cosine distance in [0, 2]; with normalised vectors typically in [0, 1].
    # Convert to a confidence score in [0, 1].
    confidence = round(max(0.0, 1.0 - top["distance"]), 4)
    manual_review = confidence < 0.5

    sources: list[str] = [h["metadata"].get("condition_id", h["id"]) for h in hits]

    if confidence < 0.3:
        return {
            "answer": "",
            "confidence": confidence,
            "manual_review": manual_review,
            "sources": sources,
        }

    fragments: list[str] = []
    for hit in hits:
        hit_confidence = round(max(0.0, 1.0 - hit["distance"]), 4)
        if hit_confidence < 0.3:
            break
        section = hit["metadata"].get("title", "")
        excerpt = hit["document"][:400]
        fragment = f"[{section}]\n{excerpt}" if section else excerpt
        fragments.append(fragment)

    answer = "\n\n".join(fragments)

    return {
        "answer": answer,
        "confidence": confidence,
        "manual_review": manual_review,
        "sources": sources,
    }


@mcp.tool()
def generate_sql_query(question: str) -> str:
    """Translate a natural-language question into a SQL SELECT statement.

    Use this tool when merchant-specific structured data is needed and
    ``merchant_dispute_lookup`` does not provide the required granularity.
    Pass the returned SQL string directly to ``execute_sql_query``.

    Args:
        question: Plain-English question about dispute data
                  (e.g. "disputes for merchant M123 with reason code 10.4").

    Returns:
        A SQL SELECT statement string ready to pass to ``execute_sql_query``.

    Raises:
        ValueError: If no template matches the question.
    """
    return sql_generator.generate_sql(question)


@mcp.tool()
def execute_sql_query(sql: str) -> list[dict]:
    """Execute a read-only SQL SELECT statement against the disputes database.

    Only SELECT statements are permitted; any other statement type raises a
    ``ValueError`` before touching the database.

    Args:
        sql: A SQL SELECT statement (typically produced by ``generate_sql_query``).

    Returns:
        List of rows as dictionaries keyed by column name.

    Raises:
        ValueError: If ``sql`` is not a SELECT statement.
    """
    return sqlite_store.execute_readonly(sql)


def main() -> None:
    import os

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        # Use Streamable HTTP (modern MCP spec) — served at /mcp
        mcp.run(transport="http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
