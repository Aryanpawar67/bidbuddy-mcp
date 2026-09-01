# BidBuddy MCP — Gap Analysis & Roadmap

_Audited: 2026-09-01 · Baseline commit: 61f2da1_

---

## How to Read This

Each gap has:
- **Impact** — how often it blocks real work (Daily / Per-bid / Occasional)
- **Effort** — implementation cost (S = ~1 day, M = 2–4 days, L = week+)
- **Fix type** — what kind of change is needed (Instruction / New tool / Logic)

---

## Priority 1 — Blocks daily RFI workflow

### GAP-01 · No RFI-stage chat input handler

**Impact**: Daily · **Effort**: S · **Fix type**: Instruction + docstring

**Problem**

When a user resolves a `[CONFIRM]` row or provides a clarification in plain chat
("Row 19 — the NPS answer is: we support it via star-rating feedback after each
assessment"), Claude has no instruction to:
1. Recognise this as an RFI patch input
2. Call `fill_rfi_xlsx` with only the affected rows
3. Call `inspect_rfi_xlsx` to confirm the write

Claude responds conversationally. The XLSX is never updated. The information is
lost at session end.

**Scenarios this covers**
- User resolves one or more `[CONFIRM]` rows
- User corrects a previously auto-filled answer
- User pastes a clarification received from internal SME / product team
- User says "update row X to say Y"

**Suggested fix**

Add a docstring block to `fill_rfi_xlsx` (and/or the `parse_rfi_xlsx` output footer)
that explicitly says:

> "If the user provides an answer for a specific row in chat — whether resolving a
> [CONFIRM] or correcting an existing fill — call fill_rfi_xlsx immediately with
> only those rows in answers_json, then call inspect_rfi_xlsx to verify.
> Do NOT respond conversationally and defer — update the file first, confirm,
> then summarise to the user."

Also add a `save_rfi_context` tool (see GAP-03) so the input is persisted even
if the XLSX write fails.

---

### GAP-02 · No surgical single-row RFI patch — undocumented

**Impact**: Daily · **Effort**: S · **Fix type**: Docstring + example

**Problem**

`fill_rfi_xlsx` technically accepts a single-element `answers_json` array (one row
update), but this is nowhere documented, guided, or shown by example. Analysts
and Claude don't know it's possible, so every correction results in either:
- `reset_rfi_filled` + full refill of all rows (slow, risky)
- Nothing (the correction never happens)

**Suggested fix**

Add an explicit example to the `fill_rfi_xlsx` Args block showing a single-row
patch call. Add a guidance note: _"To update one row without disturbing others,
pass a single-element array with that row's sheet, row number, and new answer.
The tool patches only targeted rows — all other cells remain unchanged."_

---

### GAP-03 · `save_explicit_asks` is RFP-stage only; no stage-agnostic input persistence

**Impact**: Daily · **Effort**: S · **Fix type**: New tool (small)

**Problem**

New information arrives at every stage — not just RFP:
- Qual stage: discovery call notes, champion briefing, competitor intel
- RFI stage: resolved [CONFIRM] items, SME clarifications, client emails
- Proposal stage: late pricing inputs, reference customer requests

`save_explicit_asks` is docstring-labeled _"RFP stage"_ and saves to `RFP/`.
`save_deal_insights` expects a Strengths / Weaknesses / Win-Strategy format.

Neither is right for free-form mid-RFI inputs. Claude has no clear home for them
and will either (a) drop them or (b) force-fit them into the wrong tool.

**Suggested fix**

New tool: `save_deal_note(deal_id, stage, note_text)`

- `stage`: one of `qual | rfi | rfp | general`
- Appends to `Deal Notes/{stage}_notes.md` (auto-created)
- Loaded by `get_deal_context` alongside existing context files
- Used by Claude whenever the user provides any free-form input not covered by a
  dedicated tool

`save_explicit_asks` stays as-is for structured RFP asks — `save_deal_note` is
the catch-all for everything else.

---

## Priority 2 — Significant friction per bid

### GAP-04 · No client questionnaire response ingestion

**Impact**: Per-bid · **Effort**: M · **Fix type**: New tool

**Problem**

`save_supplier_questionnaire` generates the clarification XLSX sent to the client.
When the client fills it back, there is no tool to:
- Read their responses out of the returned XLSX
- Surface those responses to Claude so they inform RFI answers and the proposal
- Persist them so they load in future sessions

Currently the analyst reads the client's responses manually, re-types key points
into chat, and they disappear at session end.

**Suggested fix**

New tool: `ingest_supplier_response(deal_id, xlsx_path)`

- Reads column 4 ("Client Response") from the returned XLSX
- Pairs each response with its question
- Saves a structured summary to `RFI/Supplier Questionnaire/client_responses.md`
- `get_deal_context` loads this file automatically
- Claude can then reference client-stated priorities when answering the RFI

---

### GAP-05 · No second-document ingestion (addenda, amendments, email attachments)

**Impact**: Per-bid · **Effort**: M · **Fix type**: New tool / extend `ingest_rfp`

**Problem**

`ingest_rfp` is one-shot and expects a single PDF. Real bids frequently include:
- Client addenda / scope amendments after the original RFP
- Updated evaluation criteria sent mid-process
- Email threads from procurement with new requirements
- Technical annexes as separate PDFs

There is no path to ingest these. The analyst pastes text into chat and it
is lost at session end.

**Suggested fix**

Extend `ingest_rfp` to accept an optional `label` parameter and append to
`rfp_text.txt` rather than overwriting it, clearly separating sections:

```
## Original RFP — [date]
...

## Addendum 1 — [label] — [date]
...
```

Or add a dedicated `ingest_addendum(deal_id, pdf_path, label)` tool that appends
to the same file. `get_deal_context` already loads `rfp_text.txt`, so downstream
tools (proposal, RFI) pick it up automatically.

---

### GAP-06 · No proposal revision workflow

**Impact**: Per-bid · **Effort**: L · **Fix type**: Logic + versioning

**Problem**

Once `generate_proposal_docx` runs, there is no way to:
- Revise specific sections based on reviewer feedback
- Track versions (v1 vs v2 vs final)
- Regenerate only changed sections without rewriting the whole document

Every revision requires a full re-run of `generate_proposal_docx` with an updated
`intake_json`. There is no diff, no section-level edit, no version history.

**Suggested fix**

- `generate_proposal_docx` should auto-version output files:
  `iMocha_Accenture_TM_Proposal_v1.docx`, `_v2.docx`, etc.
- Add a `revision_notes` parameter to `generate_proposal_docx` so the analyst
  can pass reviewer feedback and Claude incorporates it in the next run
- `save_explicit_asks` already appends (not overwrites) — this pattern works for
  iterative feedback capture; document it explicitly for proposal revision use

---

## Priority 3 — Lower frequency, quality-of-life

### GAP-07 · No deal status / lifecycle tracking

**Impact**: Occasional · **Effort**: S · **Fix type**: Logic

**Problem**

`list_deals` shows stage completion flags but no bid outcome. There is no way to:
- Mark a deal as Submitted / Under Evaluation / Won / Lost / Abandoned
- Filter `list_deals` by outcome
- Track win rate across deals

**Suggested fix**

Add `update_deal_status(deal_id, status)` that writes `status` to `meta.json`.
`list_deals` output includes the status column. Valid statuses:
`active | submitted | won | lost | abandoned`

---

### GAP-08 · `save_deal_insights` format is too rigid for qual-stage verbal inputs

**Impact**: Occasional · **Effort**: S · **Fix type**: Docstring

**Problem**

`save_deal_insights` expects a Strengths / Weaknesses / Win-Strategy markdown
structure. If the analyst verbally briefs Claude from a discovery call in free-form
("They have 50k employees in APAC, Workday is their HRIS, they care most about
skill gap reporting"), the tool forces a structure that may not fit.

**Suggested fix**

Loosen the docstring: make the Strengths/Weaknesses/Win-Strategy format a
_recommendation_, not a requirement. Allow free-form appending. Or route
free-form qual-stage inputs to `save_deal_note` (GAP-03) with `stage="qual"`.

---

### GAP-09 · No activity / decision log per deal

**Impact**: Occasional · **Effort**: S · **Fix type**: Auto-append in tools

**Problem**

There is no record of what happened in each session: which tools ran, what
decisions were made, what the analyst approved. When a second analyst picks up
the deal or when the team does a retrospective, there is no audit trail.

**Suggested fix**

Each tool that writes a deal file should auto-append a one-line entry to
`Deal Notes/activity_log.md`:

```
2026-09-01 14:32 · fill_rfi_xlsx · 33 rows answered · sheet: Parameters · col: N
2026-09-01 14:35 · inspect_rfi_xlsx · 10 rows verified
```

No new tool needed — just a `_append_activity_log(deal_id, entry)` helper called
at the end of each tool's return.

---

## Summary Table

| # | Gap | Impact | Effort | Fix Type |
|---|-----|--------|--------|----------|
| 01 | RFI chat input not routed to XLSX | Daily | S | Instruction |
| 02 | Single-row patch undocumented | Daily | S | Docstring |
| 03 | No stage-agnostic input persistence | Daily | S | New tool |
| 04 | Client questionnaire response not ingested | Per-bid | M | New tool |
| 05 | No second-document ingestion | Per-bid | M | Extend tool |
| 06 | No proposal revision workflow | Per-bid | L | Logic |
| 07 | No deal status tracking | Occasional | S | Logic |
| 08 | `save_deal_insights` too rigid | Occasional | S | Docstring |
| 09 | No activity log | Occasional | S | Helper |

---

_Next: implement GAP-01, GAP-02, GAP-03 together — they share a common theme
(routing chat inputs correctly) and can ship as one small commit._
