# AGENTS.md 
Instruction material for AI coding agents (GitHub Copilot, Claude, etc.)
working on this repository.

---

## Project purpose

A **read-only MCP server** that surfaces VIsa dipute  Model two structured tools. The agent reasoning loop
lives entirely in the **MCP client** (GitHub Copilot, Claude Desktop, …).
This server is the data and retrieval layer only — no LLM calls are made
server-side.

---

## Repository layout

```
src/card_issues/
  server.py          ← FastMCP tool definitions (authoritative interface)
  chroma_store.py    ← ChromaDB wrapper for semantic search
  sqlite_store.py    ← SQLAlchemy DDL + CRUD helpers
  sql_generator.py   ← NL → SQL template engine
  ingest.py          ← PDF → ChromaDB + SQLite ingestion pipeline

scripts/
  seed.py   ← Seeds demo  data into SQLite

data/
  visa-guidelines.pdf        ← Source PDF (not committed — add locally)
  chroma/            ← Persisted ChromaDB vector store (generated)
  merchant.db        ← SQLite database (generated)
```

---

## Tool contract (never break these signatures)

| Tool | Python signature | Returns |
|---|---|---|
| `visa_rules_search` | `(transaction_type: str, reason_code: str, evidence_flags: list[str])` | `list[dict]` — matching rule sections with rule_id, section, summary, reference |
| `merchant_dispute_lookup` | `(merchant_id: str)` | `dict` — total_disputes, recent_disputes list, resolution_stats |
| `kb_fallback` | `(question: str)` | `dict` — answer, confidence score, manual_review flag |

All tools are synchronous and return JSON-serialisable values. Do not add
`async` to tool functions without updating the FastMCP configuration.

---

## Technology choices

| Concern | Choice | Rationale |
|---|---|---|
| MCP server | `fastmcp` | Pythonic, minimal boilerplate |
| Vector store | `chromadb` (persistent) | Local, no external service |
| Embeddings | `chromadb` `DefaultEmbeddingFunction` (`all-MiniLM-L6-v2` via ONNXRuntime) | No PyTorch / CUDA required |
| Relational DB | SQLite via `sqlalchemy` | Zero-config, file-based |
| PDF parsing | `pdfplumber` | Handles visa guidelines multi-column layout |
| Data transforms | `polars` | All ingestion transforms use Polars DataFrames |
| Package manager | `uv` | Fast, reproducible, single lock file |

---

## Coding conventions

- Python ≥ 3.11. Use `from __future__ import annotations` in every module.
- All data transformations in `ingest.py` and array/table operations in
  `sql_generator.py` must use **Polars** — never pandas.
- Format with `ruff format`, lint with `ruff check --fix`.
- No secrets in source — all paths come from environment variables loaded
  via `python-dotenv` (see `.env.example`).
- `execute_sql_query` must reject any non-SELECT statement before touching
  the database. The guard is in `sqlite_store.py::execute_readonly`.
- Interactions table has a UNIQUE constraint on `(drug_a, drug_b)`. Always
  use `upsert_interaction`, never raw INSERT in new code.

---

## Development commands

```bash
# Install all dependencies (creates .venv automatically)
uv sync

# Run the MCP server — stdio transport (default for MCP clients)
uv run visa-guidelines

# Run with FastMCP dev inspector — browser UI on http://localhost:5173
uv run fastmcp dev src/visa-guidelines/server.py

# Lint + format
uv run ruff check --fix src/
uv run ruff format src/

# Tests
uv run pytest
```

---

## Data pipeline commands

```bash
# 1. Place visa-guidelines.pdf in data/
cp /path/to/visa-guidelines.pdf data/visa-guidelines.pdf

# 2. Run ingestion (PDF → ChromaDB + SQLite)
uv run python -m visa-guidelines.ingest

# 3. Seed demo merchant data
uv run python scripts/seed.py
```

---

## Agent reasoning flow

The MCP client is expected to follow this sequence:

```
clinical scenario (free text)
  └─► search_drug_monographs      ← always first; returns ranked candidates
        └─► get_full_monograph     ← call for each relevant candidate (1-N)
              ├─► check_interactions   ← if two or more drugs in the scenario
              └─► generate_sql_query   ← only when merchant-specific data needed
                    └─► execute_sql_query
                          └─► emit structured recommendation:
                                RECOMMEND | CONTRAINDICATED | USE WITH CAUTION
                                + clinical reasoning
```

---

## Extending the system

### Adding a new tool
1. Define it as a `@mcp.tool()` decorated function in `server.py`.
2. Add its signature to the Tool contract table above.
3. Write a unit test in `tests/`.

### Improving NL→SQL coverage
Add a new `(pattern, template)` tuple to `_TEMPLATES` in `sql_generator.py`.
Pattern groups must exactly match the `{placeholder}` names in the template.

### Changing the embedding model
Update `EMBEDDING_MODEL` in `chroma_store.py`, then re-run ingestion so the
collection is rebuilt with the new model's vector space.

---

## MCP client configuration

```json
{
  "mcpServers": {
    "visa-guidelines": {
      "command": "uv",
      "args": ["run", "visa-guidelines"],
      "cwd": "/absolute/path/to/visa-guidelines"
    }
  }
}
```

For **GitHub Copilot in VS Code**, place this in `.vscode/mcp.json`.