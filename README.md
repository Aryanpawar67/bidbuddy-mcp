# BidBuddy

iMocha's AI pre-sales assistant, connected to Claude Desktop.

---

## Before you start — get these from your admin

> ⚠️ These are **not** in this folder. Your team lead/admin will share them directly.

- **14 KB documents** — the product knowledge files
- **Project Instructions** — the text you paste into the Claude project

Do not download these from anywhere else.

---

## First-time setup

### What you need on your Mac
- Claude Desktop → download at **claude.ai/download** if not already installed
- Python → download at **python.org/downloads** if not already installed
- The `bidbuddy-mcp` folder on your Desktop (this folder, shared by your admin)

---

### Step 1 — Open Terminal

Press **⌘ Space**, type **Terminal**, press **Enter**.

A black or white window will open. That's the Terminal. Keep it open.

---

### Step 2 — Run the setup script

In the Terminal window, type this exactly and press **Enter**:

```
bash ~/Desktop/bidbuddy-mcp/setup.sh
```

Press **Enter** when the script asks you to. It will tell you everything it's doing and what to do if something goes wrong.

When it finishes, you'll see a green checkmark: `✓ Setup complete!`

---

### Step 3 — Restart Claude Desktop

Press **⌘Q** in Claude Desktop to quit it, then reopen it from your Applications folder.

> Look for the **🔨 icon** in the chat input bar.
> If you see it, BidBuddy is connected and ready.

---

### Step 4 — Create the BidBuddy Project in Claude Desktop

Do this once inside Claude Desktop:

1. Click **New Project** in the left sidebar
2. Name it **BidBuddy**

---

### Step 5 — Add the KB files

1. Inside the BidBuddy project, click **Add Content**
2. Upload all 14 KB documents your admin gave you
3. Wait for the upload to finish (a progress bar will show)

---

### Step 6 — Add the Project Instructions

1. Inside the BidBuddy project, find **Project Instructions** (or Custom Instructions)
2. Paste the full instructions text your admin gave you
3. Save

---

### Done ✓

Open a new chat inside the BidBuddy project. You're ready to go.

---

## Daily use — what to say

Open a chat in the **BidBuddy project** and type any of these:

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

## Where to find your files

After BidBuddy runs, everything lands in the deal folder on your Desktop:

```
Desktop/
  Accenture/
    Deal Qualification/
      iMocha_Accenture_RFPAnalysis.docx       ← RFP breakdown
      iMocha_Accenture_BidQualResult.docx     ← qualification score
    RFI/
      Supplier Questionnaire/
        iMocha_Accenture_Clarification.xlsx   ← questions to send client
      Auto Answer/
        rfi_filled.xlsx                       ← completed client questionnaire
        answers.md                            ← answer audit log
    RFP/
      iMocha_Accenture_TA_Proposal_DRAFT.docx ← final proposal
```

---

## Something went wrong?

| Problem | What to do |
|---|---|
| 🔨 icon not showing after restart | Run `setup.sh` again, then restart Claude Desktop |
| "Python not found" in setup | Download Python from python.org/downloads, then re-run setup.sh |
| Script fails on Step 2 | Screenshot the error and send to your team lead |
| Claude gives a wrong answer | Flag it with `[CONFIRM:]` and send to your team lead to update the KB |
