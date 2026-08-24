# BidBuddy

iMocha's pre-sales workflow assistant, connected to Claude Desktop via MCP.

---

## First-time setup (~5 minutes)

You need to do this once when you get a new laptop.

### Step 1 — Get the files

Ask your team lead to share the `bidbuddy-mcp` folder and drop it on your Desktop.

> Your folder path should look like: `/Users/yourname/Desktop/bidbuddy-mcp/`

---

### Step 2 — Run the setup script

1. Press **⌘ Space**, type **Terminal**, press Enter
2. Type this exactly and press Enter:

```
bash ~/Desktop/bidbuddy-mcp/setup.sh
```

The script will:
- Check Python is installed (tells you what to do if not)
- Install required packages automatically
- Configure Claude Desktop to connect to BidBuddy

> If Python isn't installed, the script will tell you — download from **python.org/downloads**, install it, and run the script again.

---

### Step 3 — Restart Claude Desktop

Quit Claude Desktop (⌘Q) and reopen it.

You should see a **🔨 icon** in the chat input bar — that means BidBuddy tools are connected.

---

### Step 4 — Set up the BidBuddy Project (one-time)

This is done inside Claude Desktop:

1. Click **New Project** in the left sidebar
2. Name it **BidBuddy**
3. Click **Add Content** → upload all 14 KB documents (get these from your team lead)
4. Click **Project Instructions** → paste the instructions block (get this from your team lead)

That's it. You're ready.

---

## Daily use — what to say

You always work inside the **BidBuddy** project in Claude Desktop.

### Start a new deal
```
New deal. Client: Accenture. Folder is at /Users/yourname/Desktop/Accenture/
Product: TA. Deadline: 30 Sep 2026.
My name: Aryan Pawar, aryan.pawar@imocha.io
```

### Qualify a deal
```
Qualify the Accenture deal.
```

### Generate supplier questionnaire
```
Generate a supplier questionnaire for Accenture.
```

### Answer a client RFI
```
The client sent us a questionnaire. File is at /Users/yourname/Downloads/Accenture_RFI.xlsx
Auto-answer it for the Accenture deal.
```

### Generate a proposal DOCX
```
Generate the proposal DOCX for Accenture.
```

---

## Deal folder structure (auto-created by BidBuddy)

Drop your client's folder on Desktop. BidBuddy creates all subfolders.

```
Desktop/
  Accenture/
    Deal Qualification/
      iMocha_Accenture_RFPAnalysis.docx     ← auto-generated
      iMocha_Accenture_BidQualResult.docx   ← auto-generated with score
    RFI/
      Supplier Questionnaire/
        iMocha_Accenture_Clarification.xlsx ← questions iMocha sends to client
      Auto Answer/
        rfi_original.xlsx                   ← client's questionnaire (untouched)
        rfi_filled.xlsx                     ← auto-answered copy
        answers.md                          ← audit trail of answers + confidence
    RFP/
      iMocha_Accenture_TA_Proposal_DRAFT.docx  ← branded proposal
```

---

## KB Documents (upload these to the Project)

| # | File | Covers |
|---|------|--------|
| 1 | TA_Analytics_.docx | TA analytics features |
| 2 | TA_Fn_Requriment.docx | TA functional requirements |
| 3 | Conversational AI Interviews.docx | AI interview product (Tara) |
| 4 | SI_Fn_Requirement.docx | Skills Intelligence features |
| 5 | SI_Reporting/Analytics | SI reporting features |
| 6 | Technical 1.docx | Architecture, APIs, integrations |
| 7 | Security.docx | Security posture, certs, hosting |
| 8 | SSO.docx | SSO and access management |
| 9 | Support & Project Management.docx | Support tiers, SLAs |
| 10 | Ethical AI.docx | AI ethics and fairness |
| 11 | Company_Overview.docx | Company background |
| 12 | LLM Skills Inferencing.docx | Skills taxonomy and LLM inference |
| 13 | AI Governance.docx | AI governance framework |
| 14 | AI FAQ Responses.docx | Common AI-related Q&A |
| 15 | iMocha_AI_Inference_Engine.pdf | AI inference mechanics (shared TA+SI) |

---

## Troubleshooting

**🔨 icon not showing in Claude Desktop**
→ Make sure you restarted Claude Desktop after running setup.sh
→ Run setup.sh again, then restart

**"Python not found" during setup**
→ Download Python from python.org/downloads (get the latest version for macOS)
→ Run setup.sh again after installing

**Tool errors in chat**
→ Ask your team lead — they can check the server logs
