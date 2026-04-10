# Card Issues — Visa Dispute MCP Server

A **read-only MCP server** that surfaces Visa dispute-management guidelines and merchant dispute history through three structured tools. The agent reasoning loop lives entirely in the **MCP client** (GitHub Copilot, Claude Desktop, …). This server is the data and retrieval layer only — no LLM calls are made server-side.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.11 |
| [uv](https://docs.astral.sh/uv/) | latest |

---

## Installation

```bash
# Clone the repository
git clone https://github.com/charlydime/cardissues.git
cd cardissues

# Install all dependencies (creates .venv automatically)
uv sync
```

---

## Environment variables

Copy `.env.example` and adjust the paths if needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `PDF_PATH` | `data/visa-guidelines.pdf` | Path to the Visa guidelines PDF |
| `CHROMA_PATH` | `data/chroma` | ChromaDB persistence directory |
| `DB_PATH` | `data/merchant.db` | SQLite database file |

---

## Data pipeline

Run these steps once (or whenever source data changes):

```bash
# 1. Place the Visa guidelines PDF in data/
cp /path/to/visa-guidelines.pdf data/visa-guidelines.pdf

# 2. Ingest the PDF into ChromaDB + SQLite
uv run python -m card_issues.ingest

# 3. Seed demo merchant data into SQLite
uv run python scripts/seed.py
```

---

## Running the server

```bash
# stdio transport — default for MCP clients
uv run visa-guidelines

# FastMCP dev inspector — browser UI at http://localhost:5173
uv run fastmcp dev src/card_issues/server.py
```

---

## MCP client configuration

Add the following to your MCP client config. For **GitHub Copilot in VS Code**, place it in `.vscode/mcp.json`.

```json
{
  "mcpServers": {
    "visa-guidelines": {
      "command": "uv",
      "args": ["run", "visa-guidelines"],
      "cwd": "/absolute/path/to/cardissues"
    }
  }
}
```

---

## MCP tools

### `visa_rules_search`

Find applicable Visa rule sections for a dispute case using semantic search over the ingested PDF.

| Parameter | Type | Description |
|---|---|---|
| `transaction_type` | `str` | Type of transaction, e.g. `"card-present"` or `"card-not-present"` |
| `reason_code` | `str` | Visa dispute reason code, e.g. `"10.4"` or `"13.1"` |
| `evidence_flags` | `list[str]` | Evidence indicators present in the case, e.g. `["signed_receipt", "avs_match"]` |

**Returns:** `list[dict]` — up to 5 matching rule sections, each containing:
- `rule_id` — rule identifier
- `section` — section title
- `summary` — truncated section text (≤ 400 chars)
- `reference` — human-readable citation string

---

### `merchant_dispute_lookup`

Retrieve dispute history and resolution statistics for a specific merchant.

| Parameter | Type | Description |
|---|---|---|
| `merchant_id` | `str` | Unique merchant identifier |

**Returns:** `dict` with:
- `total_disputes` (int) — lifetime dispute count
- `recent_disputes` (list of dicts) — each with `date`, `reason_code`, `resolution`
- `resolution_stats` (dict) — counts per resolution outcome

---

### `kb_fallback`

Answer a free-text question from the Visa dispute knowledge base. Use this when `visa_rules_search` and `merchant_dispute_lookup` do not fully address the query, or when the user asks a general policy question.

| Parameter | Type | Description |
|---|---|---|
| `question` | `str` | Plain-English question about Visa dispute rules or procedures |

**Returns:** `dict` with:
- `answer` (str) — best-effort KB answer, or empty string when unknown
- `confidence` (float) — match confidence score between `0.0` and `1.0`
- `manual_review` (bool) — `true` when confidence is too low for automation (< 0.5)

---

## Development commands

```bash
# Lint and auto-fix
uv run ruff check --fix src/

# Format
uv run ruff format src/

# Run tests
uv run pytest
```

---

## Repository layout

```
src/card_issues/
  server.py          ← FastMCP tool definitions
  chroma_store.py    ← ChromaDB wrapper for semantic search
  sqlite_store.py    ← SQLAlchemy DDL + CRUD helpers
  ingest.py          ← PDF → ChromaDB + SQLite ingestion pipeline

scripts/
  seed.py            ← Seeds demo merchant data into SQLite

data/
  visa-guidelines.pdf        ← Source PDF (not committed — add locally)
  chroma/                    ← Persisted ChromaDB vector store (generated)
  merchant.db                ← SQLite database (generated)
```
