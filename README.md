# BidBuddy

iMocha's AI pre-sales assistant, connected to Claude Desktop. BidBuddy automates the full bid lifecycle — RFP qualification, RFI auto-answering, and proposal generation — directly inside Claude Desktop via a local MCP server.

---

## Before you start — get these from your admin

> These are **not** in this repository. Your admin will share them directly.

- **14 KB documents** — iMocha product knowledge files (upload to the Claude project)
- **Project Instructions** — the text you paste into Claude Desktop's project settings

---

## First-time setup (new Mac)

### Prerequisites

| Requirement | How to get it |
|---|---|
| **Claude Desktop** | Download at [claude.ai/download](https://claude.ai/download) |
| **Git** | Run `git --version` in Terminal — macOS will prompt you to install it |

You do **not** need to install Python manually. The setup script handles everything else.

---

### Step 1 — Install Git (if needed)

Open **Terminal** (⌘ Space → type "Terminal" → Enter) and run:

```bash
git --version
```

If Git is not installed, a macOS popup will appear — click **Install** and wait ~2 minutes. Then continue.

---

### Step 2 — Clone the repository

```bash
cd ~/Desktop
git clone https://github.com/Aryanpawar67/bidbuddy-mcp.git
```

This downloads BidBuddy into `~/Desktop/bidbuddy-mcp/`.

---

### Step 3 — Run setup

```bash
bash ~/Desktop/bidbuddy-mcp/setup.sh
```

The script walks through 5 steps automatically:

| Step | What it does |
|---|---|
| 0 | Confirms Git is installed; pulls the latest code |
| 1 | Checks Claude Desktop is installed |
| 2 | Installs `uv` (manages Python and packages) |
| 3 | Downloads BidBuddy's dependencies |
| 4 | Writes BidBuddy into Claude Desktop's config and reopens the app |

Takes about **1–2 minutes**. Do not close the Terminal window.

---

### Step 4 — Enable BidBuddy in Claude Desktop

Once Claude Desktop reopens:

1. In the chat bar, click the **+** button
2. Go to **Connectors** (or Browse Connectors)
3. Find **BidBuddy** and toggle it **ON**

> If BidBuddy is not listed, quit Claude (⌘Q), reopen it, and try again.

---

### Step 5 — Create the BidBuddy project

1. Click **New Project** in the left sidebar
2. Name it **BidBuddy**
3. Upload all **14 KB documents** your admin gave you
4. Paste the **Project Instructions** text into the project instructions field

---

### Done ✓

Open a new chat inside the **BidBuddy project**. You're ready to go.

---

## Staying up to date

When your admin pushes updates, run in Terminal:

```bash
cd ~/Desktop/bidbuddy-mcp && git pull
bash ~/Desktop/bidbuddy-mcp/setup.sh
```

The setup script also auto-pulls on every run, so running `setup.sh` is usually enough.

---

## Daily use — what to say

Open a chat in the **BidBuddy project** and use prompts like these:

**Start a new deal**
```
New deal. Client: Accenture. Folder: /Users/yourname/Desktop/Accenture/
Product: TA. Deadline: 30 Sep 2026.
My name: Your Name, your.email@imocha.io
```

**Qualify a deal**
```
Qualify the Accenture deal.
```

**Generate discovery questions to send the client**
```
Generate a supplier questionnaire for Accenture.
```

**Answer a questionnaire the client sent us**
```
The client sent us a questionnaire. File is at /Users/yourname/Downloads/Accenture_RFI.xlsx
Auto-answer it for the Accenture deal.
```

**Generate the proposal DOCX**
```
Generate the proposal DOCX for Accenture.
```

---

## Deal folder layout

Everything BidBuddy produces lands in the deal folder on your Desktop:

```
Desktop/
  Accenture/
    Deal Qualification/
      iMocha_Accenture_RFPAnalysis.docx        ← RFP breakdown
      iMocha_Accenture_BidQualResult.docx      ← GO/NO-GO scorecard
    RFI/
      Supplier Questionnaire/
        iMocha_Accenture_Clarification.xlsx    ← questions to send to client
      Auto Answer/
        rfi_filled.xlsx                        ← completed client questionnaire
        answers.md                             ← answer audit log
    RFP/
      iMocha_Accenture_TA_Proposal_DRAFT.docx  ← final proposal
```

---

## How it works

```
Claude Desktop (BidBuddy project)
  ├── Project Instructions     ← shared by admin, pasted in once
  ├── 14 KB files              ← iMocha product knowledge, uploaded once
  └── MCP: BidBuddy server     ← this repo, runs locally via server.py
```

All AI reasoning happens inside Claude Desktop. The MCP server (`server.py`) is pure file I/O — it reads RFPs and RFI spreadsheets from disk and writes outputs back. No data leaves your machine except to Anthropic's Claude API.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| BidBuddy not listed in Connectors after setup | Quit Claude (⌘Q), reopen, check Connectors again |
| Setup fails at Step 2 (uv install) | Check internet connection, run `setup.sh` again |
| Setup fails at Step 3 (add-ons) | Check internet connection, run `setup.sh` again |
| `git clone` fails | Make sure Git is installed (`git --version`) and you have repo access |
| Claude gives a wrong or incomplete answer | Flag it with `[CONFIRM:]` in your message and notify your admin to update the KB |
| Need to re-run setup after an update | `cd ~/Desktop/bidbuddy-mcp && git pull && bash setup.sh` |
