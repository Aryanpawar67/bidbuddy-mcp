# BidBuddy MCP Server

iMocha pre-sales bid workflow automation for Claude Desktop.

---

## One-time setup (per laptop, ~10 minutes)

### 1. Install Python dependencies
```bash
cd ~/Desktop/bidbuddy-mcp
pip install -r requirements.txt
```

### 2. Templates are already included
`templates/TA_Proposal_template.docx` and `TM_Proposal_template.docx` are in this folder.

### 3. Configure Claude Desktop
Open (or create): `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "bidbuddy": {
      "command": "python3",
      "args": ["/Users/YOUR_NAME/Desktop/bidbuddy-mcp/server.py"]
    }
  }
}
```

Replace `YOUR_NAME` with your macOS username.

### 4. Restart Claude Desktop
Quit and reopen. You'll see a 🔨 icon in the chat input — BidBuddy tools are live.

---

## Deal folder structure (auto-created by BidBuddy)

The analyst creates a folder on Desktop (e.g. `Desktop/Accenture/`) and drops the RFP PDF in it.
BidBuddy creates all subfolders automatically:

```
Desktop/
  Accenture/
    meta.json                          ← deal metadata (auto-created)
    Deal Qualification/
      rfp.pdf                          ← original RFP (copied in)
      rfp_text.txt                     ← extracted text (auto)
      analysis.md                      ← RFP Analysis doc (Claude-authored)
      scorecard.md                     ← Qualification Scorecard with score (Claude-authored)
    RFI/
      Supplier Questionnaire/
        questionnaire.md               ← discovery questions iMocha sends to client
      Auto Answer/
        rfi_original.xlsx              ← client's questionnaire (copied in)
        rfi_filled.xlsx                ← auto-answered responses (Claude-authored)
        answers.md                     ← narrative summary of answers
    RFP/
      proposal_draft.md                ← proposal content (Claude-authored)
      iMocha_Accenture_TA_Proposal_DRAFT.docx  ← branded DOCX (generated)
```

---

## Tools available

| Tool | What it does |
|---|---|
| `setup_deal` | Initialize deal workspace + subfolders |
| `list_deals` | See all active deals and their stage |
| `get_deal_context` | Load full context for Claude (RFP + all stage outputs) |
| `ingest_rfp` | Copy RFP PDF → extract text for Claude |
| `save_output` | Save Claude's output to correct subfolder |
| `list_deal_files` | Show deal file tree |
| `parse_rfi_xlsx` | Read client's RFI questionnaire |
| `fill_rfi_xlsx` | Write answers into the questionnaire XLSX |
| `generate_proposal_docx` | Generate branded DOCX from Claude's content |

---

## Analyst workflow (what to say in Claude Desktop)

### Start a new deal
```
I have a new deal. The folder is at /Users/aryan/Desktop/Accenture/ and the RFP is inside it.
Here are the details:
- Client: Accenture
- Product: TA
- Deadline: 30 Sep 2026
- My name: Aryan Pawar, aryan.pawar@imocha.io
- Prepared for: Global Procurement Team, Accenture
```
Claude will call `setup_deal` and `ingest_rfp` automatically.

### Deal Qualification
```
Qualify the Accenture deal.
```
Claude calls `get_deal_context`, reads the RFP, generates RFP Analysis + Qualification Scorecard
(10 parameters, score out of 100), saves both docs, returns the score in chat.

### Supplier Questionnaire (discovery questions iMocha sends to client)
```
Generate a supplier questionnaire for Accenture to send to the client.
```
Claude generates structured discovery questions (technical, commercial, timeline gaps),
saves to `RFI/Supplier Questionnaire/questionnaire.md`.

### RFI Auto-Answer (client sends iMocha a vendor questionnaire)
```
The client sent us a vendor questionnaire. File is at /Users/aryan/Downloads/Accenture_RFI.xlsx
Auto-answer it for the Accenture deal.
```
Claude parses the XLSX, answers all questions using KB + RFP context, fills the sheet,
saves `rfi_filled.xlsx` with [CONFIRM:] markers for anything uncertain.

### Proposal Generation
```
Generate the proposal DOCX for Accenture.
```
Claude reads all prior context (RFP + qualification + RFI answers), authors proposal content,
generates the branded DOCX with yellow highlights, saves to `RFP/`.

---

## Claude Desktop project instructions (paste into BidBuddy project)

```
You are iMocha's pre-sales AI assistant. You have BidBuddy tools connected.

When an analyst starts a new deal, ask for:
1. Client name
2. Product (TA or TM)
3. RFP PDF path (or folder path)
4. Deadline
5. Their name and email (SPOC)
6. Client procurement contact name/team

Then call setup_deal and ingest_rfp in sequence.

## DEAL QUALIFICATION — 10 parameters, score each /10, total /100

1.  Strategic Fit — does this client's need match TA or TM exactly?
2.  Budget Signal — is budget indicated and does it meet our floor?
3.  Relationship — do we have an existing relationship or warm intro?
4.  Win Probability — are we positioned to win vs incumbents?
5.  Effort Required — how much pre-sales effort will this take?
6.  Timeline Feasibility — can we meet the submission and delivery dates?
7.  Compliance Requirements — can we meet all stated compliance/legal requirements?
8.  Product Readiness — do we have all required features/integrations?
9.  Reference Availability — do we have relevant case studies for this client's industry?
10. Commercial Viability — is the deal size and structure commercially viable?

Save analysis with save_output(stage="analysis") and scorecard with save_output(stage="scorecard", qualification_score=<total>).

Return the score summary in chat.

## SUPPLIER QUESTIONNAIRE
Generate structured discovery questions grouped by: Technical, Integration, Commercial, Timeline, Evaluation Criteria.
These are questions iMocha sends TO the client to clarify gaps before committing to a proposal.
Save with save_output(stage="supplier_questionnaire").

## RFI AUTO-ANSWER
Use KB docs in this project + deal context from get_deal_context.
Answer every question. Mark [CONFIRM: reason] for anything not traceable to KB or RFP.
Never guess pricing, legal terms, or implementation timelines.
Save narrative summary with save_output(stage="rfi_answers").
Fill the XLSX with fill_rfi_xlsx.

## PROPOSAL GENERATION
Use get_deal_context — it includes RFP + qualification + RFI answers.
Author intake JSON, call generate_proposal_docx.
All AI-authored sections get yellow highlights in Word.
[CONFIRM:] marks anything the analyst must fill before sending.

## Flagging rule
Anything not traceable to KB docs, the RFP, or confirmed bid context → [CONFIRM: description].
Never fabricate capabilities, certifications, pricing, or case study metrics.

## iMocha capabilities
[Upload the 12-15 KB docs as project files — Claude reads them directly]
```
