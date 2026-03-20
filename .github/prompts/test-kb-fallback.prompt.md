---
description: "Test the kb_fallback MCP tool with a free-text Visa dispute question"
name: "Test kb_fallback"
argument-hint: "Plain-English question about Visa dispute rules or procedures"
agent: "agent"
tools: ["visa-guidelin/kb_fallback"]
---

Call the `kb_fallback` tool with the following question:

"${input:question:Plain-English question about Visa dispute rules or procedures (e.g. What evidence is required to respond to a Condition 10.4 dispute?)}"

After the tool returns, report:
- **Answer**: the text returned (or note if empty)
- **Confidence**: the score (0.0 – 1.0) and what it means (≥ 0.5 = automated, < 0.5 = manual review recommended)
- **Manual review required**: yes/no

If `manual_review` is `true`, suggest a more specific follow-up query or recommend calling `visa_rules_search` instead.
