# BidBuddy MCP — Project Context for Claude

_Last updated: 2026-09-01 · Current HEAD: 2023460_

---

## What This Is

BidBuddy is an MCP server (`server.py`) that automates iMocha's pre-sales bid
workflow inside Claude Desktop. It handles the full lifecycle from RFP intake
through proposal generation. Claude Desktop is the AI brain; the MCP tools are
pure file I/O — they read/write deal folders on disk and return structured text
back to Claude for reasoning.

**The KB files (14 documents) and project instructions live in the Claude Desktop
project, not in this repo.** They are identical for both MCP and non-MCP usage.

---

## Architecture

```
Claude Desktop (BidBuddy project)
  ├── Project Instructions     ← same for MCP and non-MCP flows
  ├── 14 KB files              ← iMocha product knowledge (uploaded, not in repo)
  └── MCP: BidBuddy server     ← server.py via fastmcp
        └── Tools (file I/O only — no AI logic inside tools)
```

All AI reasoning happens in Claude. Tools only:
- Read files from disk and return their content to Claude
- Write content Claude has already generated into the right files
- Return structured metadata Claude uses to decide next steps

---

## Deal Folder Layout

Every deal lives under `BIDS_DIR` (default: `~/Desktop`):

```
{client_name}/
  meta.json                                  ← deal metadata (id, stage, product type)
  Deal Qualification/
    rfp.pdf                                  ← original RFP
    rfp_text.txt                             ← extracted text (loaded by get_deal_context)
    qualification_summary.md                 ← qual analysis + scorecard
    deal_insights.md                         ← strengths / risks / win strategy
  RFI/
    Supplier Questionnaire/
      iMocha_{client}_RFI_Clarification.xlsx ← sent TO client
      questionnaire_summary.md               ← summary (loaded by get_deal_context)
    Auto Answer/
      rfi_original.xlsx                      ← original — NEVER MODIFIED
      rfi_structure.json                     ← column map from parse_rfi_xlsx
      rfi_col_map.json                       ← per-sheet answer column mapping
      rfi_filled.xlsx                        ← working file with iMocha's answers
      answers.md                             ← audit log of all fills
  RFP/
    explicit_asks.md                         ← late-breaking client requirements
    proposal_draft.md                        ← markdown draft
    iMocha_{client}_{TA|TM}_Proposal_DRAFT.docx
```

`get_deal_context` loads these files (in order) to rebuild deal state:
1. `rfp_text.txt`
2. `qualification_summary.md`
3. `deal_insights.md`
4. `questionnaire_summary.md`
5. `answers.md`
6. `explicit_asks.md`
7. `proposal_draft.md`

**Always call `get_deal_context` at the start of any session on an existing deal.**

---

## Tool Inventory

### Deal management
| Tool | When to call |
|------|-------------|
| `setup_deal` | Once per deal — creates folder structure, writes meta.json |
| `list_deals` | To see all active deals with stage and score |
| `get_deal_context` | Start of every session on an existing deal |
| `list_deal_files` | To see what's in a deal folder |

### RFP ingestion & qualification
| Tool | When to call |
|------|-------------|
| `ingest_rfp` | After setup — copies PDF, extracts text, returns it for Claude to read |
| `classify_deal` | After ingestion — auto-detects TA / TM / Both, saves to meta.json |
| `save_rfp_analysis_docx` | After reading RFP — generates 11-section RFP Analysis DOCX |
| `save_qual_result_docx` | After scoring — GO/NO-GO doc with 10 criteria and win strategy |
| `save_deal_insights` | Immediately after delivering insights in chat — persists them |

### RFI — Supplier Questionnaire (outgoing)
| Tool | When to call |
|------|-------------|
| `save_supplier_questionnaire` | To generate clarification questions XLSX to send to client |

### RFI — Auto-Answer (incoming client questionnaire)
| Tool | When to call | Notes |
|------|-------------|-------|
| `parse_rfi_xlsx` | Step 1 — load and map the client's XLSX | Always confirm structure before Step 2 |
| `fill_rfi_xlsx` | Step 2 — write answers into rfi_filled.xlsx | NEVER touches rfi_original.xlsx |
| `inspect_rfi_xlsx` | After every fill — verify cell writes | Always run after fill_rfi_xlsx |
| `reset_rfi_filled` | When fills are in the wrong column | Deletes rfi_filled.xlsx for a clean restart |
| `save_output` | Only for `rfi_answers` stage | Saves answers.md audit log |

### Proposal
| Tool | When to call |
|------|-------------|
| `generate_proposal_docx` | Final stage — needs get_deal_context first |
| `save_explicit_asks` | Before proposal gen — persist any late-breaking client requirements |

### Legacy / deprecated
| Tool | Status |
|------|--------|
| `save_qualification_docx` | Deprecated — use `save_qual_result_docx` instead |
| `save_output` with `analysis`/`scorecard`/`supplier_questionnaire` stages | Will error — those stages removed |

---

## RFI Auto-Answer Flow — Step by Step

```
1. parse_rfi_xlsx(deal_id, xlsx_path)
      → returns sheet structure, detected columns, question list
      → saves rfi_original.xlsx (never touch this again)

2. USER CONFIRMS the column mapping (question col, answer col)

3. fill_rfi_xlsx(deal_id, answers_json, answer_col, sheet_type)
      → answers_json: JSON array of {sheet, row, answer, confidence}
      → confidence: "high" | "medium" | "low"
      → patches ONLY targeted rows — all other cells preserved

4. inspect_rfi_xlsx(deal_id)
      → reads actual cell values to verify fills landed correctly

5. If wrong column: reset_rfi_filled(deal_id) → go back to step 3

6. save_output(deal_id, "rfi_answers", answers_md)
      → saves the audit log
```

**If the user provides a chat input resolving a `[CONFIRM]` row or correcting an
answer mid-session:** call `fill_rfi_xlsx` immediately with only that row in
`answers_json`, then call `inspect_rfi_xlsx`. Do not respond conversationally
and defer — update the file first.

Single-row patch example:
```json
[{"sheet": "Parameters", "row": 19, "answer": "iMocha supports NPS via...", "confidence": "high"}]
```

---

## Answering Quality Rules (RFI)

The `fill_rfi_xlsx` docstring carries the full instruction set. Key points:

- **Cross-section synthesis required** — bring proof points (Tara, iMocha Projects,
  Assessment Agent, Capgemini, Deloitte, SLA numbers, Supademo links) from any KB
  section into any answer where they are relevant.
- **Sales-consultant depth** — direct opener (Yes/Partial/No), named bullet
  sub-sections, concrete numbers, customer references, demo links.
- **`[CONFIRM]` only for KB-silent topics** — commercial pricing, TBD placeholders,
  scope-specific items. Never write `[CONFIRM]` in a cell for product capabilities
  the KB covers even partially; use the status badge for those instead.
- **Sheet type detection** fires at score ≥ 3 keyword matches. Scores of 1–2
  fall back to `general_rfi` to prevent misclassification of general capability
  sheets as dedicated technical questionnaires.

---

## Key Invariants — Never Break These

1. **`rfi_original.xlsx` is never modified.** `fill_rfi_xlsx` always copies from
   original to `rfi_filled.xlsx` on first run, then patches the filled file.

2. **`fill_rfi_xlsx` patches surgically.** It writes only to specified rows in
   specified columns. It does not reformat, delete, or rewrite other cells.

3. **`get_deal_context` is the single source of truth for deal state.** All
   downstream tools (proposal, RFI) must call it first in a new session.

4. **`deal_id` = client name exactly as passed to `setup_deal`.** Case-sensitive.
   The folder name on disk IS the deal_id.

5. **`save_explicit_asks` appends — it never overwrites.** Safe to call multiple
   times across sessions.

6. **Templates live in `templates/`.** `TA_Proposal_template.docx` and
   `TM_Proposal_template.docx` — do not rename or move.

7. **`BIDS_DIR` defaults to `~/Desktop`.** Can be overridden via env var if needed.

---

## Product Classification

iMocha has two products. The deal type controls which proposal template is used:

- **TA** — Talent Acquisition / Skills Assessment (hiring, candidates, ATS)
- **TM** — Talent Management / Skills Intelligence (employees, skills, L&D)
- **Both** — deal spans both

`classify_deal` auto-detects from RFP text. The result is saved in `meta.json`
and used by `generate_proposal_docx` to select the right template.

---

## Sheet Type Detection

`_detect_sheet_type` classifies incoming RFI sheets to apply appropriate
answering rules. Detection uses keyword scoring across 6 types:

| Type | Examples |
|------|---------|
| `risk_assessment` | RTO, RPO, incident, BCP, disaster recovery |
| `ai_security` | ML model, bias, explainability, hallucination |
| `data_privacy` | GDPR, CCPA, data subject, DPA |
| `compliance` | ISO 27001, SOC 2, audit, certification |
| `security` | encryption, TLS, firewall, MFA, SIEM |
| `technical_spec` | API, SLA, webhook, SSO, infrastructure |
| `general_rfi` | fallback (score < 3) |

Each type has its own ANSWERING RULES in `_SHEET_TYPE_GUIDANCE`. The base
answering instruction in `fill_rfi_xlsx`'s docstring applies to all types.

---

## Environment & Dependencies

```
Python 3.10+
fastmcp >= 2.0.0     ← MCP server framework
pypdf >= 4.0.0       ← PDF text extraction
openpyxl >= 3.1.0    ← Excel read/write
python-docx          ← DOCX generation (via docx_engine.py)
```

Setup: `bash ~/Desktop/bidbuddy-mcp/setup.sh`

Claude Desktop config: `~/Library/Application Support/Claude/claude_desktop_config.json`
MCP entry: `bidbuddy` → `python server.py`

---

## Known Issues & Gaps

See `GAPS.md` for the full prioritised list. Top 3 to be aware of:

- **GAP-01**: Chat inputs (resolved `[CONFIRM]` rows, SME clarifications) are not
  automatically routed to `fill_rfi_xlsx`. Must be done manually by calling the
  tool with just the affected rows.
- **GAP-03**: No stage-agnostic input persistence. `save_deal_insights` is for
  qual-stage structured content; `save_explicit_asks` is for RFP-stage asks.
  There is no free-form note tool for RFI-stage inputs yet.
- **GAP-04**: No tool to ingest the client's filled-back supplier questionnaire.

---

## Commit History Reference

```
2023460  docs: add GAPS.md — 9 gaps, prioritised
61f2da1  improve: KB-sourced synthesis replaces word-for-word retrieval
d1d70f5  feat: inspect_rfi_xlsx + reset_rfi_filled tools
bce3fef  fix: answer_col override + parse re-entry crash
9e16e03  fix: char-limit rejection instead of silent truncation
```

---

## What NOT to Do

- Do not modify `rfi_original.xlsx` — ever.
- Do not call `save_qualification_docx` — it's deprecated; use `save_qual_result_docx`.
- Do not call `save_output` with `analysis`, `scorecard`, or `supplier_questionnaire`
  stages — those will error.
- Do not skip `parse_rfi_xlsx` and call `fill_rfi_xlsx` directly — the col map
  won't exist and fills will land in the wrong column.
- Do not skip `inspect_rfi_xlsx` after filling — silent write failures have happened.
- Do not add AI logic inside MCP tools. Tools are file I/O only; reasoning stays
  in Claude.
