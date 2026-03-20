---
description: "Test the visa_rules_search MCP tool with a dispute case scenario"
name: "Test visa_rules_search"
argument-hint: "Dispute case details: transaction type, reason code, and evidence flags"
agent: "agent"
tools: ["visa-guidelin/visa_rules_search"]
---

Call the `visa_rules_search` tool with the following dispute case:

- **transaction_type**: "${input:transaction_type:Type of transaction (e.g. card-present, card-not-present, e-commerce)}"
- **reason_code**: "${input:reason_code:Visa dispute reason code (e.g. 10.4, 13.1, 12.5)}"
- **evidence_flags**: ["${input:evidence_flags:Comma-separated evidence indicators (e.g. signed_receipt, avs_match, 3ds_authenticated)}"]

After the tool returns, report for each matching rule section:
- **Rule ID**: the identifier of the matched rule
- **Section**: the rule section title
- **Summary**: the first 400 characters of the rule text
- **Reference**: the source document reference

If no results are returned, suggest refining the `reason_code` or broadening the `evidence_flags`, and recommend calling `kb_fallback` with a plain-English question as a fallback.
