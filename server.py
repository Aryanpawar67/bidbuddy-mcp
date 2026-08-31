#!/usr/bin/env python3
"""
BidBuddy MCP Server — iMocha pre-sales bid workflow automation.
Tools handle file operations only. Claude Desktop + project KB handles all AI reasoning.
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

# ── Config ─────────────────────────────────────────────────────────────────────
# BIDS_DIR: root folder where all deal folders live (defaults to ~/Desktop)
# Analyst creates Desktop/Accenture/ → server creates subfolders inside it
BIDS_DIR = Path(os.environ.get("BIDS_DIR", Path.home() / "Desktop"))
TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", Path(__file__).parent / "templates"))

mcp = FastMCP("BidBuddy")

# ── Product classification keywords ───────────────────────────────────────────
# TA = Talent Acquisition / Skills Assessment (hiring, candidates, ATS)
# TM = Talent Management / Skills Intelligence (employees, skills architecture)
_TA_KEYWORDS = [
    "talent acquisition", "skills assessment", "skills assessments",
    "ai interview", "ai interviews", "video interview", "video interviews",
    "ats integration", "applicant tracking",
    "oracle recruiting", "oracle taleo",
    "workday recruiting", "workday ats",
    "smartrecruiters", "smart recruiters",
    "icims", "greenhouse recruiting", "sap recruiting", "successfactors recruiting",
    "proctoring", "online proctoring", "remote proctoring",
    "coding assessment", "coding assessments", "coding test",
    "candidate experience", "candidate journey",
    "campus recruiting", "campus hiring", "lateral hiring", "lateral recruit",
    "volume hiring", "high-volume hiring",
    "pre-employment", "pre employment",
    "hiring assessment", "recruitment assessment",
]

_TM_KEYWORDS = [
    "talent management", "skills intelligence",
    "skills inventory", "skill inventory",
    "skills taxonomy", "skill taxonomy",
    "skills ontology", "skill ontology",
    "competency framework", "competency model",
    "skills validation", "skill validation",
    "manager validation",
    "self assessment", "self-assessment",
    "skills gap", "skill gap", "gap analysis",
    "learning recommendation", "learning recommendations",
    "upskill", "reskill", "re-skill",
    "internal mobility",
    "career pathing", "career path",
    "workforce planning",
    "succession planning", "succession management",
    "ai skills inference", "skills inference",
    "skills intelligence analytics", "skills analytics",
    "job role to skill", "role-skill mapping",
    "skills ontology", "skills architecture",
    "employee skills", "workforce skills",
    "workday hcm", "sap successfactors hcm",
]


def _classify_product(text: str) -> dict:
    """
    Score text against TA and TM keyword lists.
    Returns {"product_type": "TA"|"TM"|"Both"|"unknown", "ta_hits": [...], "tm_hits": [...]}
    """
    lower = text.lower()
    ta_hits = sorted({kw for kw in _TA_KEYWORDS if kw in lower})
    tm_hits = sorted({kw for kw in _TM_KEYWORDS if kw in lower})

    ta = len(ta_hits)
    tm = len(tm_hits)

    if ta == 0 and tm == 0:
        product_type = "unknown"
    elif ta > 0 and tm == 0:
        product_type = "TA"
    elif tm > 0 and ta == 0:
        product_type = "TM"
    elif ta >= tm * 2:
        product_type = "TA"   # TA dominant (2× more hits)
    elif tm >= ta * 2:
        product_type = "TM"   # TM dominant
    else:
        product_type = "Both"

    return {"product_type": product_type, "ta_hits": ta_hits, "tm_hits": tm_hits}


# ── Folder structure ───────────────────────────────────────────────────────────
#
#  {BIDS_DIR}/
#    Accenture/
#      meta.json
#      Deal Qualification/
#        rfp.pdf
#        rfp_text.txt
#        analysis.md
#        scorecard.md
#      RFI/
#        Supplier Questionnaire/
#          questionnaire.md
#        Auto Answer/
#          rfi_original.xlsx
#          rfi_structure.json
#          rfi_filled.xlsx
#          answers.md
#      RFP/
#        proposal_draft.md
#        iMocha_Accenture_TA_Proposal_DRAFT.docx

SUBFOLDERS = [
    "Deal Qualification",
    "RFI/Supplier Questionnaire",
    "RFI/Auto Answer",
    "RFP",
]

STAGE_FILES = {
    "rfi_answers":    "RFI/Auto Answer/answers.md",
    "proposal_draft": "RFP/proposal_draft.md",
}

CONTEXT_FILES = [
    ("Deal Qualification/rfp_text.txt",                    "## RFP Content"),
    ("Deal Qualification/qualification_summary.md",        "## Deal Qualification Summary"),
    ("Deal Qualification/deal_insights.md",                "## Deal Strengths & Insights"),
    ("RFI/Supplier Questionnaire/questionnaire_summary.md","## Supplier Questionnaire (summary)"),
    ("RFI/Auto Answer/answers.md",                         "## RFI Auto-Answer Summary"),
    ("RFP/explicit_asks.md",                               "## Customer Explicit Asks"),
    ("RFP/proposal_draft.md",                              "## Proposal Draft"),
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert client name to safe folder name, preserving spaces for readability."""
    return re.sub(r"[<>:/\\|?*\"']", "", name).strip()

def _deal_path(deal_id: str) -> Path:
    return BIDS_DIR / deal_id

def _load_meta(deal_id: str) -> dict:
    # Direct lookup first (fast path: deal folder is directly inside BIDS_DIR)
    p = _deal_path(deal_id) / "meta.json"
    if p.exists():
        return json.loads(p.read_text())
    # Fallback: scan all subdirs for a matching deal_id in meta.json
    # Handles deals whose folder was provided via folder_path or named differently
    for d in BIDS_DIR.iterdir():
        mf = d / "meta.json"
        if mf.exists():
            try:
                m = json.loads(mf.read_text())
                if m.get("deal_id") == deal_id:
                    return m
            except Exception:
                continue
    raise ValueError(f"Deal '{deal_id}' not found. Use list_deals to see active deals.")

def _save_meta(deal_id: str, meta: dict) -> None:
    (_deal_path(deal_id) / "meta.json").write_text(json.dumps(meta, indent=2))

def _create_subfolders(base: Path) -> None:
    for sub in SUBFOLDERS:
        (base / sub).mkdir(parents=True, exist_ok=True)

# ── Specialized sheet-type detection ──────────────────────────────────────────
_SHEET_TYPE_SIGNALS: dict = {
    "risk_assessment": [
        "risk", "threat", "vulnerability", "incident", "disaster recovery", "bcp",
        "business continuity", "rto", "rpo", "pentest", "penetration test",
        "third party risk", "vendor risk", "supply chain", "residual risk",
        "risk register", "risk rating", "inherent risk",
    ],
    "ai_security": [
        "artificial intelligence", "machine learning", "ml model", "model governance",
        "bias", "explainability", "fairness", "hallucination", "llm",
        "generative ai", "training data", "ai ethics", "responsible ai",
        "model accuracy", "model drift", "ai transparency", "algorithmic",
    ],
    "data_privacy": [
        "gdpr", "ccpa", "data subject", "right to erasure", "dpia",
        "data processing agreement", "personal data", "data retention",
        "data protection officer", "dpo", "privacy", "lawful basis",
        "consent", "data minimization",
    ],
    "compliance": [
        "iso 27001", "soc 2", "soc2", "nis2", "nist", "pci dss",
        "hipaa", "audit", "certification", "accreditation",
        "regulatory", "compliance framework", "caiq", "sig lite",
    ],
    "security": [
        "encryption", "aes", "tls", "ssl", "firewall", "intrusion detection",
        "ids", "ips", "vulnerability scan", "patch management",
        "access control", "mfa", "multi-factor", "zero trust",
        "siem", "endpoint security", "network security",
    ],
    "technical_spec": [
        "api", "integration", "webhook", "sso", "saml", "oauth",
        "latency", "uptime", "sla", "hosting", "infrastructure",
        "architecture", "scalability", "throughput", "availability",
        "response time", "rate limit",
    ],
}

_SHEET_TYPE_LABELS = {
    "risk_assessment": "Risk Assessment",
    "ai_security":     "AI / ML Security",
    "data_privacy":    "Data Privacy / GDPR",
    "compliance":      "Compliance & Certifications",
    "security":        "Information Security",
    "technical_spec":  "Technical Specification",
    "general_rfi":     "General RFI / Features",
}

_SHEET_TYPE_GUIDANCE = {
    "risk_assessment": """\
ANSWERING RULES — Risk Assessment
  • Never assert RTO, RPO, uptime %, or incident timelines unless the exact figure is in a KB source file.
  • Use confidence 'low' + [CONFIRM:CONTRACTUAL] for SLA numbers, DR capabilities, or audit results.
  • Do not infer compliance from certifications unless the cert explicitly covers the control asked about.
  • Every claim about pen tests or third-party audits requires a dated KB reference.
  → Recommended KB files to load: security_posture, compliance_certs, incident_response""",

    "ai_security": """\
ANSWERING RULES — AI / ML Security
  • Do not claim 'no hallucinations', 'fully explainable', or 'unbiased' — unprovable absolutes.
  • Use confidence 'medium' for model governance / bias mitigation unless ai_governance KB is loaded.
  • Training data provenance, contamination, model versioning → confidence 'low' + [CONFIRM:AI-GOVERNANCE] unless in KB.
  • Describe what the product does; avoid performance claims without benchmarks.
  → Recommended KB files to load: ai_governance, security_posture""",

    "data_privacy": """\
ANSWERING RULES — Data Privacy / GDPR
  • GDPR / CCPA / DPIA claims must be sourced from KB — never inferred from general knowledge.
  • Data subject rights (access, erasure, portability) → confirm exact workflow from KB; if absent use [CONFIRM:LEGAL].
  • Data retention periods must match KB exactly — do not estimate.
  • Cross-border transfer claims → [CONFIRM:LEGAL] if SCCs/BCRs not in KB.
  → Recommended KB files to load: data_privacy, compliance_certs""",

    "compliance": """\
ANSWERING RULES — Compliance & Certifications
  • Only name certificates (ISO 27001, SOC 2, etc.) if they appear in KB with a certificate number or audit date.
  • For NIS2 / NIST / CAIQ / SIG Lite, do not map internal controls to framework controls unless KB does so explicitly.
  • [CONFIRM:COMPLIANCE] for any question about audit scope, last audit date, or remediation timelines.
  → Recommended KB files to load: compliance_certs, security_posture""",

    "security": """\
ANSWERING RULES — Information Security
  • Encryption algorithms, key lengths, TLS versions → must match KB exactly.
  • Pen test / vulnerability scan results → [CONFIRM:SECURITY] unless KB contains a dated summary.
  • MFA / SSO claims are safe to assert from integrations KB.
  • SIEM, EDR, SOC details → source from security_posture KB only.
  → Recommended KB files to load: security_posture, compliance_certs""",

    "technical_spec": """\
ANSWERING RULES — Technical Specification
  • API rate limits, uptime SLAs, latency figures → source from KB only.
  • Integration claims must match integrations KB — do not name a connector unless listed there.
  • Hosting / infrastructure → source from security_posture KB.
  • Custom development timelines → [CONFIRM:TECHNICAL] unless pre-approved.
  → Recommended KB files to load: integrations, security_posture, pricing_terms""",

    "general_rfi": """\
ANSWERING RULES — General RFI
  • Source answers from product KB and deal context; cross-section synthesis is encouraged.
  • Write comprehensive, structured, sales-quality answers — not brief summaries.
  • confidence 'high' for direct KB coverage; write full detail with proof points.
  • confidence 'medium' when KB partially covers the topic; write the best answer available.
  • confidence 'low' + [CONFIRM: <what to verify>] ONLY when KB is completely silent
    (commercial pricing, TBD items, out-of-scope platform questions); never for product capabilities.""",
}


def _detect_sheet_type(sheet_name: str, headers: list, section_names: list) -> str:
    """Score all text signals against type keyword lists; return the winning type."""
    combined = " ".join([sheet_name] + headers + section_names).lower()
    scores: dict = {t: 0 for t in _SHEET_TYPE_SIGNALS}
    for stype, signals in _SHEET_TYPE_SIGNALS.items():
        for sig in signals:
            if sig in combined:
                scores[stype] += 1
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] >= 3 else "general_rfi"


# ── Deal management ────────────────────────────────────────────────────────────

@mcp.tool()
def setup_deal(
    client_name: str,
    product: str,
    deadline: str,
    spoc_name: str,
    spoc_email: str,
    prepared_for: str = "",
    rfp_title: str = "",
    folder_path: str = "",
) -> str:
    """
    Set up a deal workspace. Creates the full subfolder structure (Deal Qualification,
    RFI/Supplier Questionnaire, RFI/Auto Answer, RFP) inside the deal folder.

    If the analyst already created the folder (e.g. Desktop/Accenture), pass its
    full path as folder_path. Otherwise the server creates it under BIDS_DIR.

    Args:
        client_name:  Client company name, e.g. "Accenture"
        product:      "TA" or "TM"
        deadline:     Submission deadline, e.g. "2026-09-30"
        spoc_name:    iMocha sales SPOC full name
        spoc_email:   iMocha sales SPOC email
        prepared_for: Client procurement contact name/title (optional)
        rfp_title:    Short RFP/bid title (optional)
        folder_path:  Full path to an existing deal folder (optional — skips creation)
    """
    if product not in ("TA", "TM"):
        return "Error: product must be 'TA' or 'TM'."

    deal_id = _slugify(client_name)

    if folder_path:
        base = Path(folder_path)
        if not base.exists():
            return f"Error: folder not found at {folder_path}"
        # If the analyst named it differently, use that name as deal_id
        deal_id = base.name
        # Ensure it's also accessible via BIDS_DIR (symlink or just track by full path)
        # We'll store the absolute path in meta so tools can find it
    else:
        base = BIDS_DIR / deal_id
        base.mkdir(parents=True, exist_ok=True)

    _create_subfolders(base)

    meta = {
        "deal_id":    deal_id,
        "base_path":  str(base),
        "client_name": client_name,
        "rfp_title":  rfp_title or f"{client_name} {product} RFP",
        "product":    product,
        "deadline":   deadline,
        "spoc_name":  spoc_name,
        "spoc_email": spoc_email,
        "prepared_for": prepared_for or f"Procurement Team, {client_name}",
        "stage":      "deal_qualification",
        "stages_completed": [],
        "created_at": datetime.now().isoformat(),
    }
    (base / "meta.json").write_text(json.dumps(meta, indent=2))

    return (
        f"Deal workspace ready: {base}\n\n"
        f"Folders created:\n"
        f"  {base}/Deal Qualification/\n"
        f"  {base}/RFI/Supplier Questionnaire/\n"
        f"  {base}/RFI/Auto Answer/\n"
        f"  {base}/RFP/\n\n"
        f"deal_id: {deal_id}\n"
        f"Next: run ingest_rfp to load the RFP document."
    )


@mcp.tool()
def list_deals() -> str:
    """List all active deals with their stage, score, and files."""
    deals = []
    for d in sorted(BIDS_DIR.iterdir()):
        mf = d / "meta.json"
        if not d.is_dir() or not mf.exists():
            continue
        m = json.loads(mf.read_text())
        if "deal_id" not in m:
            continue

        completed = ", ".join(m.get("stages_completed", [])) or "not started"
        score = m.get("qualification_score", "")
        score_str = f"  Score: {score}/100" if score else ""

        # Count files across subfolders
        all_files = [f for f in d.rglob("*") if f.is_file() and f.name != "meta.json"]
        deals.append(
            f"━━ {m['deal_id']}  [{m['product']}]  Deadline: {m['deadline']}\n"
            f"   Client: {m['client_name']}{score_str}\n"
            f"   Stage: {m['stage']}  |  Completed: {completed}\n"
            f"   Files: {len(all_files)} across deal subfolders"
        )

    return "\n\n".join(deals) if deals else "No deals found. Use setup_deal to create one."


@mcp.tool()
def get_deal_context(deal_id: str) -> str:
    """
    Load full deal context: metadata + RFP text + all stage outputs.
    Call this at the start of every stage so Claude has everything it needs.

    Args:
        deal_id: Client name as used in setup_deal (e.g. "Accenture")
    """
    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])

    parts = [
        f"# Deal: {meta['client_name']}",
        f"Product: {meta['product']}",
        f"RFP Title: {meta['rfp_title']}",
        f"Deadline: {meta['deadline']}",
        f"SPOC: {meta['spoc_name']} <{meta['spoc_email']}>",
        f"Prepared For: {meta['prepared_for']}",
        f"Current Stage: {meta['stage']}",
        f"Stages Completed: {', '.join(meta.get('stages_completed', [])) or 'none'}",
    ]
    if meta.get("qualification_score"):
        parts.append(f"Qualification Score: {meta['qualification_score']}/100")
    parts.append("")

    for rel_path, heading in CONTEXT_FILES:
        f = base / rel_path
        if not f.exists():
            continue
        content = f.read_text()
        if not content.strip():
            continue
        if "rfp_text" in rel_path and len(content) > 50_000:
            content = content[:50_000] + "\n\n[... RFP truncated at 50k chars ...]"
        parts.append(heading)
        parts.append(content)
        parts.append("")

    return "\n".join(parts)


@mcp.tool()
def save_output(deal_id: str, stage: str, content: str, qualification_score: int = 0) -> str:
    """
    DEPRECATED FOR MOST STAGES — use the dedicated tools instead:
      - Deal Qualification docs → save_rfp_analysis_docx + save_qual_result_docx
      - Supplier Questionnaire → save_supplier_questionnaire
      - Proposal → generate_proposal_docx

    This tool is only valid for two remaining stages:
      - rfi_answers:    saves answers.md to RFI/Auto Answer/
      - proposal_draft: saves proposal_draft.md to RFP/

    Do NOT call this with 'analysis', 'scorecard', or 'supplier_questionnaire' —
    those stages are NOT in STAGE_FILES and will return an error.

    Args:
        deal_id:             Client name (e.g. "Accenture")
        stage:               One of: rfi_answers, proposal_draft
        content:             Full markdown content to save
        qualification_score: Unused (legacy parameter — ignored)
    """
    if stage not in STAGE_FILES:
        return f"Error: stage must be one of {list(STAGE_FILES.keys())}"

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    out_path = base / STAGE_FILES[stage]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content)

    completed = meta.setdefault("stages_completed", [])
    if stage not in completed:
        completed.append(stage)

    if stage == "scorecard" and qualification_score:
        meta["qualification_score"] = qualification_score
        # Advance overall stage
        meta["stage"] = "rfi"

    if stage in ("rfi_answers",):
        meta["stage"] = "rfp"

    if stage == "proposal_draft":
        meta["stage"] = "proposal_review"

    _save_meta(deal_id, meta)

    return f"Saved to: {out_path}\n({len(content):,} chars)"


@mcp.tool()
def save_rfp_analysis_docx(deal_id: str, sections_json: str) -> str:
    """
    Generate DOC 1 — RFP Analysis (Structured Opportunity Analysis).
    11-section document: what the CLIENT needs, their objectives, requirements,
    integration landscape, risks, and where iMocha fits.
    Saves to Deal Qualification/ subfolder.

    Args:
        deal_id:       Client name (e.g. "Accenture")
        sections_json: JSON object with all 11 sections:
          {
            "customer_objectives":          ["..."],   // what client wants to achieve
            "business_drivers":             ["..."],   // why now / urgency
            "key_functional_requirements":  ["..."],   // capability categories + items
            "technical_requirements":       ["..."],   // SaaS, APIs, hosting, migration
            "compliance_requirements":      ["..."],   // security, certifications, privacy
            "integration_landscape":        ["..."],   // HRIS/ATS/LMS context
            "integration_systems":          [{"name":"Workday","category":"HCM","details":"used for employee data sync"}],
            "implementation_expectations":  ["..."],   // timeline, onboarding, UAT
            "proposal_themes":              ["..."],   // how to frame the response
            "imocha_strengths":             ["..."],   // why iMocha fits this deal
            "key_risks":                    ["..."]    // clarifications needed
          }
          All arrays are bullet lists. integration_systems is an optional named table.
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        return "Error: python-docx not installed. Run: pip install python-docx"

    try:
        sec = json.loads(sections_json)
    except json.JSONDecodeError as e:
        return f"Error: invalid sections_json — {e}"

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    dq_dir = base / "Deal Qualification"
    dq_dir.mkdir(parents=True, exist_ok=True)

    # ── BidTrack brand palette ────────────────────────────────────────────────
    C_NAVY    = "1A0A4A"
    C_PURPLE  = "491AEB"
    C_ORANGE  = "FD5B0E"
    C_PTINT   = "F0EEFF"
    C_WARN    = "B45309"
    C_WARNT   = "FFF8E8"
    C_MUTED   = "7B6FA8"
    C_INK     = "0D0820"
    C_BORDER  = "E4DFFF"
    C_MUTEDBG = "F5F4FA"
    C_WHITE   = "FFFFFF"

    def _rgb(h: str) -> RGBColor:
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def _shd(cell, fill: str):
        tcPr = cell._tc.get_or_add_tcPr()
        s = OxmlElement("w:shd")
        s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), fill)
        tcPr.append(s)

    def _border_spec(style="single", size=4, color=C_BORDER):
        return {"style": "single", "size": size, "color": color, "space": 0}

    def _no_border_cell(cell):
        tcPr = cell._tc.get_or_add_tcPr()
        tcBdr = OxmlElement("w:tcBorders")
        for side in ["top", "left", "bottom", "right"]:
            b = OxmlElement(f"w:{side}")
            b.set(qn("w:val"), "none")
            tcBdr.append(b)
        tcPr.append(tcBdr)

    doc = Document()
    section = doc.sections[0]
    section.page_width  = Cm(21); section.page_height = Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.3)
    section.top_margin  = section.bottom_margin = Cm(2)
    doc.styles["Normal"].paragraph_format.space_before = Pt(0)
    doc.styles["Normal"].paragraph_format.space_after  = Pt(0)

    def _heading(num: int, title: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18); p.paragraph_format.space_after = Pt(6)
        r = p.add_run(f"{num}. {title}")
        r.font.name = "Calibri"; r.font.size = Pt(13); r.font.bold = True
        r.font.color.rgb = _rgb(C_NAVY)

    def _bullet(text: str):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        r = p.runs[0] if p.runs else p.add_run(text)
        if not p.runs:
            pass
        else:
            r.text = text
        if not r.text:
            p.add_run(text)
        r2 = p.add_run("") if not p.runs else None
        # Clear and re-add
        for run in p.runs:
            run.text = ""
        r = p.add_run(text)
        r.font.name = "Calibri"; r.font.size = Pt(10); r.font.color.rgb = _rgb(C_INK)

    def _bullet_clean(text: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.5)
        r = p.add_run("•  " + text)
        r.font.name = "Calibri"; r.font.size = Pt(10); r.font.color.rgb = _rgb(C_INK)

    # ── Title block ────────────────────────────────────────────────────────────
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(f"RFP Analysis – {meta['client_name']} ({meta['product']})")
    r.font.name = "Calibri"; r.font.size = Pt(22); r.font.bold = True
    r.font.color.rgb = _rgb(C_NAVY)

    p2 = doc.add_paragraph()
    p2.paragraph_format.space_before = Pt(0); p2.paragraph_format.space_after = Pt(2)
    r2 = p2.add_run(f"{meta['client_name']} – {meta['rfp_title']}")
    r2.font.name = "Calibri"; r2.font.size = Pt(12); r2.font.color.rgb = _rgb(C_MUTED)

    p3 = doc.add_paragraph()
    p3.paragraph_format.space_before = Pt(0); p3.paragraph_format.space_after = Pt(16)
    r3 = p3.add_run("Executive Opportunity Analysis")
    r3.font.name = "Calibri"; r3.font.size = Pt(10); r3.font.color.rgb = _rgb(C_MUTED)
    r3.font.italic = True

    # ── 1. Opportunity Overview ────────────────────────────────────────────────
    _heading(1, "Opportunity Overview")
    ov_data = [
        ("Customer",          meta["client_name"],   False),
        ("Opportunity",       meta["rfp_title"],     True),
        ("Solution Area",     {"TA": "Talent Acquisition (Skills Assessment)", "TM": "Talent Management (Skills Intelligence)"}.get(meta["product"], "Skills Platform"), False),
        ("Procurement Type",  "Competitive RFP",     True),
        ("Deadline",          meta["deadline"],      False),
        ("iMocha SPOC",       f"{meta['spoc_name']} · {meta['spoc_email']}", True),
    ]
    ov_tbl = doc.add_table(rows=len(ov_data) + 1, cols=2)
    ov_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    # Header row
    for ci, h in enumerate(["Item", "Details"]):
        c = ov_tbl.cell(0, ci)
        _shd(c, C_NAVY)
        p = c.paragraphs[0]
        p.paragraph_format.space_before = Pt(5); p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.left_indent = Cm(0.2)
        r = p.add_run(h)
        r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = True
        r.font.color.rgb = _rgb(C_WHITE)
    for ri, (label, val, tint) in enumerate(ov_data, 1):
        bg = C_PTINT if tint else C_WHITE
        lc = ov_tbl.cell(ri, 0); vc = ov_tbl.cell(ri, 1)
        _shd(lc, C_MUTEDBG); _shd(vc, bg)
        for c, text, bold in [(lc, label, True), (vc, val, False)]:
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Cm(0.2)
            r = p.add_run(text)
            r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = bold
            r.font.color.rgb = _rgb(C_MUTED if bold else C_INK)

    # ── Sections 2–9: bullets ─────────────────────────────────────────────────
    bullet_sections = [
        (2,  "Customer Objectives",             "customer_objectives"),
        (3,  "Business Drivers",                "business_drivers"),
        (4,  "Key Functional Requirements",     "key_functional_requirements"),
        (5,  "Technical Requirements",          "technical_requirements"),
        (6,  "Security & Compliance Expectations", "compliance_requirements"),
        (8,  "Implementation Expectations",     "implementation_expectations"),
        (9,  "Key Proposal Themes",             "proposal_themes"),
    ]
    for num, title, key in bullet_sections:
        if num == 7:
            # Integration landscape goes here — handled separately below
            pass
        _heading(num, title)
        for item in sec.get(key, []):
            _bullet_clean(item)

    # ── 7. Integration Landscape (inserted after section 6) ───────────────────
    _heading(7, "Integration Landscape")
    for item in sec.get("integration_landscape", []):
        _bullet_clean(item)
    int_sys = sec.get("integration_systems", [])
    if int_sys:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(4)
        r = p.add_run("⚑  Integration Systems Named in RFP  — Confirm availability before responding")
        r.font.name = "Calibri"; r.font.size = Pt(10); r.font.bold = True
        r.font.color.rgb = _rgb(C_WARN)
        int_tbl = doc.add_table(rows=len(int_sys) + 1, cols=3)
        int_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
        for ci, h in enumerate(["System / Platform", "Category", "RFP Integration Requirement"]):
            c = int_tbl.cell(0, ci)
            _shd(c, C_WARN)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Cm(0.15)
            r = p.add_run(h)
            r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = True
            r.font.color.rgb = _rgb(C_WHITE)
        for ri, sys in enumerate(int_sys, 1):
            bg = C_WARNT if ri % 2 == 0 else C_WHITE
            for ci, (val, bold, col) in enumerate([
                (sys.get("name", ""),    True,  C_INK),
                (sys.get("category",""), True,  C_WARN),
                (sys.get("details",""),  False, C_INK),
            ]):
                c = int_tbl.cell(ri, ci)
                _shd(c, bg)
                p = c.paragraphs[0]
                p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.left_indent = Cm(0.15)
                r = p.add_run(str(val))
                r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = bold
                r.font.color.rgb = _rgb(col)

    # ── 10. Why iMocha Fits + 11. Risks ───────────────────────────────────────
    _heading(10, "Why iMocha Fits This Opportunity")
    for item in sec.get("imocha_strengths", []):
        _bullet_clean(item)
    _heading(11, "Key Risks / Clarifications Required")
    for item in sec.get("key_risks", []):
        _bullet_clean(item)

    # ── Footer note ────────────────────────────────────────────────────────────
    doc.add_paragraph().paragraph_format.space_after = Pt(12)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Prepared by iMocha Bid Buddy  ·  {datetime.now().strftime('%B %d, %Y')}  ·  CONFIDENTIAL")
    r.font.name = "Calibri"; r.font.size = Pt(8); r.font.italic = True
    r.font.color.rgb = _rgb(C_MUTED)

    safe = re.sub(r"[^a-z0-9]+", "_", meta["client_name"].lower()).strip("_")
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"iMocha_{safe}_RFPAnalysis_{date_str}.docx"
    out = dq_dir / filename
    doc.save(out)

    # Write summary for get_deal_context
    summary = f"RFP Analysis: {filename}\nSections: {len([s for s in sec.values() if s])}\n"
    existing = (dq_dir / "qualification_summary.md").read_text() if (dq_dir / "qualification_summary.md").exists() else ""
    (dq_dir / "qualification_summary.md").write_text(f"## RFP Analysis\n{summary}\n{existing}")

    completed = meta.setdefault("stages_completed", [])
    if "rfp_analysis" not in completed:
        completed.append("rfp_analysis")
    _save_meta(deal_id, meta)

    return (
        f"RFP Analysis DOCX saved: {filename}\n"
        f"Location: {out}\n"
        f"Sections populated: {sum(1 for v in sec.values() if v)}/11\n\n"
        f"━━ NEXT STEP ━━\n"
        f"Now provide a deal strengths & weaknesses analysis based on the RFP content:\n"
        f"  • Top 3–5 strengths (where iMocha clearly fits)\n"
        f"  • Top 3–5 risks or gaps (integration complexity, competition, unknowns)\n"
        f"  • One-paragraph win strategy\n"
        f"  • 3–4 recommended next steps\n"
        f"Then call save_deal_insights to persist the analysis."
    )


@mcp.tool()
def save_qual_result_docx(deal_id: str, assessment_json: str) -> str:
    """
    Generate DOC 2 — Bid Qualification Result (Executive Briefing).
    Internal scoring document: 10 criteria with weights, GO/NO-GO decision badge,
    AI rationales, risks, and win strategy. For leadership review.
    Saves to Deal Qualification/ subfolder.

    Args:
        deal_id:         Client name (e.g. "Accenture")
        assessment_json: JSON object:
          {
            "scores": {
              "strategic_fit": 4, "business_problem": 3, "use_case": 4,
              "stakeholder": 3, "commercial": 4, "competitive": 3,
              "implementation": 4, "technical": 3, "proposal_risk": 3,
              "value_realization": 4
            },
            "rationales": {
              "strategic_fit": "one sentence citing RFP evidence",
              ... (one per criterion)
            },
            "executive_summary": "2-3 sentence summary paragraph",
            "strengths": ["strength 1", ...],
            "risks": ["risk 1", ...],
            "win_strategy": "2-3 sentence strategy paragraph",
            "next_steps": ["step 1", "step 2", "step 3", "step 4"],
            "decision": "go" | "conditional_go" | "no_go",
            "integration_systems": [
              {"name": "Workday", "category": "ATS/HCM", "note": "brief context from RFP"}
            ],
            "integration_complexity": "Low" | "Medium" | "High" | "Not Specified",
            "integration_notes": "one-sentence summary of integration ask"
          }
          Scores are 1–5 per criterion. decision overrides calculated threshold.
          integration_systems may be [] if no systems named in RFP.
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        return "Error: python-docx not installed. Run: pip install python-docx"

    try:
        asmnt = json.loads(assessment_json)
    except json.JSONDecodeError as e:
        return f"Error: invalid assessment_json — {e}"

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    dq_dir = base / "Deal Qualification"
    dq_dir.mkdir(parents=True, exist_ok=True)

    # ── BidTrack palette ──────────────────────────────────────────────────────
    C_NAVY   = "1A0A4A"; C_PURPLE = "491AEB"; C_ORANGE = "FD5B0E"
    C_PTINT  = "F0EEFF"; C_GO     = "1A7F3C"; C_GOTINT = "E8F8EE"
    C_WARN   = "B45309"; C_WARNT  = "FFF8E8"; C_NOGO   = "C0392B"
    C_NOGOT  = "FFF0F0"; C_MUTED  = "7B6FA8"; C_INK    = "0D0820"
    C_BORDER = "E4DFFF"; C_MBGD   = "F5F4FA"; C_WHITE  = "FFFFFF"
    # Darker selected shades for decision badge
    C_GO_D   = "0A4D23"; C_WARN_D = "7C3901"; C_NOGO_D = "7E1A1A"
    # Ghost text for non-selected badge (muted tint of each color)
    C_GO_G   = "82B898"; C_WARN_G = "C9A87A"; C_NOGO_G = "C98080"
    C_GHOST  = "F6F6F6"  # near-white bg for non-selected

    CRITERIA = [
        ("strategic_fit",    "Strategic Opportunity Fit",               0.15),
        ("business_problem", "Business Problem Clarity",                0.10),
        ("use_case",         "Use Case Alignment",                      0.10),
        ("stakeholder",      "Customer Stakeholder & Decision Readiness",0.10),
        ("commercial",       "Commercial Attractiveness",               0.10),
        ("competitive",      "Competitive Position",                    0.10),
        ("implementation",   "Implementation Feasibility",              0.10),
        ("technical",        "Technical & Security Fit",                0.10),
        ("proposal_risk",    "Proposal Risk Assessment",                0.10),
        ("value_realization","Value Realization & Expansion Potential", 0.05),
    ]

    scores = asmnt.get("scores", {})
    rationales = asmnt.get("rationales", {})
    total_score = round(sum((scores.get(cid, 0) / 5) * w * 100 for cid, _, w in CRITERIA))
    dec = asmnt.get("decision") or ("go" if total_score >= 65 else "conditional_go" if total_score >= 45 else "no_go")

    dec_color = {"go": C_GO, "conditional_go": C_WARN, "no_go": C_NOGO}.get(dec, C_WARN)
    dec_label = {"go": "GO", "conditional_go": "CONDITIONAL GO", "no_go": "NO GO"}.get(dec, "—")
    bid_strength = "Strong" if total_score >= 75 else "Moderate" if total_score >= 55 else "Weak" if total_score >= 35 else "Insufficient Data"

    def _rgb(h: str) -> RGBColor:
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def _shd(cell, fill: str):
        tcPr = cell._tc.get_or_add_tcPr()
        s = OxmlElement("w:shd")
        s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), fill)
        tcPr.append(s)

    def param_status(s: int): return "—" if s == 0 else "SUPPORTED" if s >= 4 else "PARTIAL" if s == 3 else "GAP"
    def param_col(s: int):    return C_MUTED if s == 0 else C_GO if s >= 4 else C_WARN if s == 3 else C_NOGO
    def param_tint(s: int):   return C_MBGD if s == 0 else C_GOTINT if s >= 4 else C_WARNT if s == 3 else C_NOGOT

    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21); section.page_height = Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.3)
    section.top_margin  = section.bottom_margin = Cm(2)
    doc.styles["Normal"].paragraph_format.space_before = Pt(0)
    doc.styles["Normal"].paragraph_format.space_after  = Pt(0)

    def _sec_heading(num: str, title: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18); p.paragraph_format.space_after = Pt(6)
        r1 = p.add_run(f"{num}. ")
        r1.font.name = "Calibri"; r1.font.size = Pt(13); r1.font.bold = True
        r1.font.color.rgb = _rgb(C_INK)
        r2 = p.add_run(title)
        r2.font.name = "Calibri"; r2.font.size = Pt(13); r2.font.bold = True
        r2.font.color.rgb = _rgb(C_NAVY)

    def _body(text: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(6)
        r = p.add_run(text)
        r.font.name = "Calibri"; r.font.size = Pt(10); r.font.color.rgb = _rgb(C_INK)

    def _bullet_item(text: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.5)
        r = p.add_run("•  " + text)
        r.font.name = "Calibri"; r.font.size = Pt(10); r.font.color.rgb = _rgb(C_INK)

    # ── Title block ────────────────────────────────────────────────────────────
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r1 = p.add_run(meta["client_name"] + "   ")
    r1.font.name = "Calibri"; r1.font.size = Pt(20); r1.font.bold = True
    r1.font.color.rgb = _rgb(C_PURPLE)
    r2 = p.add_run(meta.get("rfp_title", ""))
    r2.font.name = "Calibri"; r2.font.size = Pt(10); r2.font.color.rgb = _rgb(C_MUTED)

    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(4)
    r3 = p2.add_run("Bid Qualification — Executive Briefing")
    r3.font.name = "Calibri"; r3.font.size = Pt(11); r3.font.bold = True
    r3.font.color.rgb = _rgb(C_NAVY)
    r4 = p2.add_run("  ·  Audience: Leadership (CXO, Product, Sales, PreSales)")
    r4.font.name = "Calibri"; r4.font.size = Pt(9); r4.font.color.rgb = _rgb(C_MUTED)
    r4.font.italic = True

    # Decision banner paragraph
    p_dec = doc.add_paragraph()
    p_dec.paragraph_format.space_before = Pt(4); p_dec.paragraph_format.space_after = Pt(16)
    from docx.oxml import OxmlElement as OE
    pPr = p_dec._p.get_or_add_pPr()
    shd = OE("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), dec_color)
    pPr.append(shd)
    r_dec = p_dec.add_run(f"  {dec_label}    Score: {total_score} / 100  ·  Bid Strength: {bid_strength}")
    r_dec.font.name = "Calibri"; r_dec.font.size = Pt(12); r_dec.font.bold = True
    r_dec.font.color.rgb = _rgb(C_WHITE)

    # ── 1. Executive Summary ───────────────────────────────────────────────────
    _sec_heading("1", "Executive Summary")
    _body(asmnt.get("executive_summary", "No summary provided."))

    # ── 2. Customer Profile ────────────────────────────────────────────────────
    _sec_heading("2", "Customer Profile")
    profile_rows = [
        ("Customer",      meta["client_name"]),
        ("Product Line",  {"TA": "Talent Acquisition (Skills Assessment)", "TM": "Talent Management (Skills Intelligence)"}.get(meta["product"], "Skills Platform")),
        ("Deadline",      meta["deadline"]),
        ("Decision",      dec_label),
        ("Qual. Score",   f"{total_score} / 100  ({bid_strength})"),
        ("Prepared By",   meta["spoc_name"]),
        ("Date",          datetime.now().strftime("%B %d, %Y")),
    ]
    p_tbl = doc.add_table(rows=len(profile_rows), cols=2)
    p_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    for ri, (label, val) in enumerate(profile_rows):
        bg = C_PTINT if ri % 2 != 0 else C_WHITE
        lc = p_tbl.cell(ri, 0); vc = p_tbl.cell(ri, 1)
        _shd(lc, C_MBGD); _shd(vc, bg)
        for c, text, bold, col in [(lc, label, True, C_MUTED), (vc, val, False, C_INK)]:
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Cm(0.15)
            r = p.add_run(text)
            r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = bold
            r.font.color.rgb = _rgb(col)

    # ── 3. Strategic Fit ───────────────────────────────────────────────────────
    _sec_heading("3", "Strategic Fit for iMocha")
    for s in asmnt.get("strengths", []):
        _bullet_item(s)

    # ── 4. Score Breakdown ─────────────────────────────────────────────────────
    _sec_heading("4", "Qualification Score Breakdown")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("AI-generated rationale for each criterion is included in the Rationale column.")
    r.font.name = "Calibri"; r.font.size = Pt(9); r.font.italic = True
    r.font.color.rgb = _rgb(C_MUTED)

    sc_tbl = doc.add_table(rows=len(CRITERIA) + 2, cols=6)
    sc_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    # Header
    for ci, (h, w) in enumerate(zip(["#","Criterion","Score","Weight","Status","Rationale"],[3,22,6,7,9,53])):
        c = sc_tbl.cell(0, ci)
        _shd(c, C_NAVY)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
        r = p.add_run(h)
        r.font.name = "Calibri"; r.font.size = Pt(8); r.font.bold = True
        r.font.color.rgb = _rgb(C_WHITE)
    # Criteria rows
    for ri, (cid, cname, weight) in enumerate(CRITERIA):
        s = scores.get(cid, 0)
        rat = rationales.get(cid, "Not scored.")
        st = param_status(s); st_col = param_col(s); st_tint = param_tint(s)
        row_bg = C_MBGD if ri % 2 != 0 else None
        row = sc_tbl.rows[ri + 1]
        for ci, (val, align, bold, fg, bg_override) in enumerate([
            (str(ri+1),              WD_ALIGN_PARAGRAPH.CENTER, False, C_MUTED,  row_bg),
            (cname,                  WD_ALIGN_PARAGRAPH.LEFT,   True,  C_INK,    row_bg),
            (f"{s}/5" if s else "—", WD_ALIGN_PARAGRAPH.CENTER, True,  st_col,   row_bg),
            (f"{int(weight*100)}%",  WD_ALIGN_PARAGRAPH.CENTER, False, C_MUTED,  row_bg),
            (st,                     WD_ALIGN_PARAGRAPH.CENTER, True,  st_col,   st_tint),
            (rat,                    WD_ALIGN_PARAGRAPH.LEFT,   False, C_INK,    row_bg),
        ]):
            c = row.cells[ci]
            _shd(c, bg_override or C_WHITE)
            p = c.paragraphs[0]; p.alignment = align
            p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.left_indent = Cm(0.1) if align == WD_ALIGN_PARAGRAPH.LEFT else Cm(0)
            r = p.add_run(str(val))
            r.font.name = "Calibri"; r.font.size = Pt(8 if ci == 5 else 9)
            r.font.bold = bold; r.font.color.rgb = _rgb(fg)
    # Total row
    total_row = sc_tbl.rows[len(CRITERIA) + 1]
    for ci in range(6):
        _shd(total_row.cells[ci], C_NAVY)
    tc = total_row.cells[5]
    p = tc.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(5); p.paragraph_format.space_after = Pt(5)
    r = p.add_run(f"Total: {total_score} / 100")
    r.font.name = "Calibri"; r.font.size = Pt(11); r.font.bold = True
    r.font.color.rgb = _rgb(C_WHITE)

    # ── 5. Integration & Technical Snapshot ───────────────────────────────────
    _sec_heading("5", "Integration & Technical Snapshot")
    int_systems = asmnt.get("integration_systems", [])
    int_complexity = asmnt.get("integration_complexity", "Not Specified")
    int_notes = asmnt.get("integration_notes", "")

    # Complexity badge line
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(6)
    complexity_col = {"Low": C_GO, "Medium": C_WARN, "High": C_NOGO}.get(int_complexity, C_MUTED)
    r1 = p.add_run("Integration Complexity: ")
    r1.font.name = "Calibri"; r1.font.size = Pt(10); r1.font.bold = False
    r1.font.color.rgb = _rgb(C_MUTED)
    r2 = p.add_run(int_complexity)
    r2.font.name = "Calibri"; r2.font.size = Pt(10); r2.font.bold = True
    r2.font.color.rgb = _rgb(complexity_col)

    if int_notes:
        _body(int_notes)

    if int_systems:
        # Named systems table: System | Category | RFP Context
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(3)
        r = p.add_run("Named Integration Systems:")
        r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = True
        r.font.color.rgb = _rgb(C_NAVY)

        int_tbl = doc.add_table(rows=len(int_systems) + 1, cols=3)
        int_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
        for ci, (h, w) in enumerate(zip(["System / Platform", "Category", "RFP Context"], [30, 20, 50])):
            c = int_tbl.cell(0, ci)
            _shd(c, C_NAVY)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.left_indent = Cm(0.1)
            r = p.add_run(h)
            r.font.name = "Calibri"; r.font.size = Pt(8); r.font.bold = True
            r.font.color.rgb = _rgb(C_WHITE)
        for ri, sys in enumerate(int_systems):
            row_bg = C_MBGD if ri % 2 != 0 else C_WHITE
            for ci, val in enumerate([
                sys.get("name", ""),
                sys.get("category", ""),
                sys.get("note", ""),
            ]):
                c = int_tbl.cell(ri + 1, ci)
                _shd(c, row_bg)
                p = c.paragraphs[0]
                p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.left_indent = Cm(0.1)
                r = p.add_run(val)
                r.font.name = "Calibri"; r.font.size = Pt(9)
                r.font.color.rgb = _rgb(C_INK)
    else:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(4)
        r = p.add_run("No specific integration systems named in the RFP.")
        r.font.name = "Calibri"; r.font.size = Pt(9); r.font.italic = True
        r.font.color.rgb = _rgb(C_MUTED)

    # ── 6. Potential Risks ─────────────────────────────────────────────────────
    _sec_heading("6", "Potential Risks")
    for risk in asmnt.get("risks", []):
        _bullet_item(risk)

    # ── 7. Recommended Win Strategy ────────────────────────────────────────────
    _sec_heading("7", "Recommended Win Strategy")
    _body(asmnt.get("win_strategy", "No win strategy provided."))
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8); p.paragraph_format.space_after = Pt(4)
    r = p.add_run("Recommended Next Steps:")
    r.font.name = "Calibri"; r.font.size = Pt(10); r.font.bold = True
    r.font.color.rgb = _rgb(C_NAVY)
    for i, step in enumerate(asmnt.get("next_steps", []), 1):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(f"{i}.  ")
        r1.font.name = "Calibri"; r1.font.size = Pt(10); r1.font.bold = True
        r1.font.color.rgb = _rgb(C_PURPLE)
        r2 = p.add_run(step)
        r2.font.name = "Calibri"; r2.font.size = Pt(10); r2.font.color.rgb = _rgb(C_INK)

    # Decision badge row — selected: darker shade + white bold; non-selected: ghost bg + very muted text
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    badge_tbl = doc.add_table(rows=1, cols=5)
    badge_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for di, (dlabel, dcol_dark, dghost_text) in enumerate([
        ("GO",             C_GO_D,   C_GO_G),
        ("",               None,     None),
        ("CONDITIONAL GO", C_WARN_D, C_WARN_G),
        ("",               None,     None),
        ("NO GO",          C_NOGO_D, C_NOGO_G),
    ]):
        c = badge_tbl.cell(0, di)
        if not dlabel:
            _shd(c, C_WHITE)
            continue
        is_sel = (dlabel == dec_label)
        if is_sel:
            _shd(c, dcol_dark)
            p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(10)
            r = p.add_run(dlabel)
            r.font.name = "Calibri"; r.font.size = Pt(14); r.font.bold = True
            r.font.color.rgb = _rgb(C_WHITE)
        else:
            _shd(c, C_GHOST)
            p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(10)
            r = p.add_run(dlabel)
            r.font.name = "Calibri"; r.font.size = Pt(12); r.font.bold = False
            r.font.color.rgb = _rgb(dghost_text)

    # ── Save ───────────────────────────────────────────────────────────────────
    safe = re.sub(r"[^a-z0-9]+", "_", meta["client_name"].lower()).strip("_")
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"iMocha_{safe}_BidQualResult_{date_str}.docx"
    out = dq_dir / filename
    doc.save(out)

    # Internal summary for get_deal_context
    risk_count = sum(1 for cid, _, _ in CRITERIA if scores.get(cid, 0) <= 2 and scores.get(cid, 0) > 0)
    summary_lines = [
        f"Score: {total_score}/100  |  Decision: {dec_label}  |  Bid Strength: {bid_strength}",
        f"Criteria gaps/risks: {risk_count}",
        "",
        "Scores:",
    ] + [f"  {cname}: {scores.get(cid, 0)}/5  [{param_status(scores.get(cid,0))}]" for cid, cname, _ in CRITERIA]
    existing = (dq_dir / "qualification_summary.md").read_text() if (dq_dir / "qualification_summary.md").exists() else ""
    (dq_dir / "qualification_summary.md").write_text(existing + f"\n## Qualification Result\n" + "\n".join(summary_lines))

    completed = meta.setdefault("stages_completed", [])
    for s in ("analysis", "scorecard"):
        if s not in completed:
            completed.append(s)
    meta["qualification_score"] = total_score
    meta["stage"] = "rfi"
    _save_meta(deal_id, meta)

    gap_criteria = [cname for cid, cname, _ in CRITERIA if scores.get(cid, 0) in (1, 2)]
    strong_criteria = [cname for cid, cname, _ in CRITERIA if scores.get(cid, 0) >= 4]
    return (
        f"Qualification Result DOCX saved: {filename}\n"
        f"Location: {out}\n"
        f"Score: {total_score}/100  |  Decision: {dec_label}  |  Bid Strength: {bid_strength}\n"
        f"Criteria gaps ({risk_count}): {', '.join(gap_criteria) or 'none'}\n"
        f"Strong criteria: {', '.join(strong_criteria) or 'none'}\n\n"
        f"━━ NEXT STEP — Deal Insights ━━\n"
        f"Based on the scores and rationales above, now deliver a deal strengths & weaknesses briefing:\n"
        f"  • Top strengths (score 4–5 criteria + why they matter for this client)\n"
        f"  • Key risks / weaknesses (score 1–2 criteria + mitigation ideas)\n"
        f"  • Win strategy (1–2 sentences: how to position given this scorecard)\n"
        f"  • Recommended next steps (3–4 concrete actions)\n"
        f"Then call save_deal_insights to persist it so future sessions have this context."
    )


@mcp.tool()
def save_qualification_docx(
    deal_id: str,
    scorecard_json: str,
    analysis_text: str,
    recommendation: str,
    overall_score: int,
) -> str:
    """
    LEGACY — use save_qual_result_docx instead.

    save_qual_result_docx is the current preferred tool. It uses the same 10 criteria,
    produces a richer executive briefing (integration snapshot, decision badge, win strategy,
    next steps), and automatically triggers the deal insights analysis.

    This tool remains for backwards compatibility only. Do NOT call it for new deals.

    Args:
        deal_id:        Client name (e.g. "Accenture")
        scorecard_json: JSON array of 10 scored parameters:
                        [{"parameter": "Strategic Fit", "score": 8,
                          "evidence": "one-sentence KB evidence", "risk": ""}]
                        Set risk to a brief flag if score < 5, else "".
        analysis_text:  Narrative analysis — use \\n between paragraphs (≤400 words).
        recommendation: Exactly one of: "Pursue" | "Pursue with Caution" | "No-Bid"
        overall_score:  Overall weighted score out of 100.
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        return "Error: python-docx not installed. Run: pip install python-docx"

    try:
        params = json.loads(scorecard_json)
    except json.JSONDecodeError as e:
        return f"Error: invalid scorecard_json — {e}"

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    dq_dir = base / "Deal Qualification"
    dq_dir.mkdir(parents=True, exist_ok=True)

    # ── Color helpers ──────────────────────────────────────────────────────────
    def _rgb(hex6: str) -> RGBColor:
        return RGBColor(int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16))

    def _shd(cell, hex6: str):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hex6)
        tcPr.append(shd)

    def _no_border(tbl_el):
        tblPr = tbl_el.tblPr if tbl_el.tblPr is not None else OxmlElement("w:tblPr")
        borders = OxmlElement("w:tblBorders")
        for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
            b = OxmlElement(f"w:{side}")
            b.set(qn("w:val"), "none")
            borders.append(b)
        tblPr.append(borders)

    def _set_col_width(cell, cm_val):
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcW = OxmlElement("w:tcW")
        tcW.set(qn("w:w"), str(int(Cm(cm_val).emu / 914.4)))  # EMU → twips
        tcW.set(qn("w:type"), "dxa")
        tcPr.append(tcW)

    C_DARK   = "220032"
    C_PURPLE = "491AEB"
    C_ORANGE = "FD5B0E"
    C_LIGHT  = "EDE8FC"
    C_GREEN  = "0D9D58"
    C_RED    = "DC2626"
    C_TEXT   = "1A1A2E"
    C_LGREY  = "F8F6FF"

    rec_color = {"Pursue": C_GREEN, "Pursue with Caution": C_ORANGE, "No-Bid": C_RED}.get(
        recommendation, C_ORANGE
    )

    doc = Document()
    section = doc.sections[0]
    section.page_width  = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin  = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    doc.styles["Normal"].paragraph_format.space_before = Pt(0)
    doc.styles["Normal"].paragraph_format.space_after  = Pt(0)

    def _banner(text_top: str, text_main: str, bg: str):
        t = doc.add_table(rows=1, cols=1)
        _no_border(t._tbl)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        c = t.cell(0, 0)
        _shd(c, bg)
        p1 = c.paragraphs[0]
        p1.paragraph_format.space_before = Pt(12)
        p1.paragraph_format.space_after  = Pt(3)
        p1.paragraph_format.left_indent  = Cm(0.5)
        r = p1.add_run(text_top)
        r.font.name = "Calibri"; r.font.size = Pt(8)
        r.font.color.rgb = _rgb("9980CC"); r.font.bold = True
        p2 = c.add_paragraph()
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after  = Pt(12)
        p2.paragraph_format.left_indent  = Cm(0.5)
        r2 = p2.add_run(text_main)
        r2.font.name = "Calibri"; r2.font.size = Pt(20)
        r2.font.color.rgb = _rgb("FFFFFF"); r2.font.bold = True

    def _section_heading(text: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after  = Pt(6)
        r = p.add_run(text)
        r.font.name = "Calibri"; r.font.size = Pt(9)
        r.font.bold = True; r.font.color.rgb = _rgb(C_DARK)

    # ── Title banner ───────────────────────────────────────────────────────────
    _banner("iMocha BidBuddy", "Deal Qualification Report", C_DARK)

    # ── Meta strip: 4-column table ─────────────────────────────────────────────
    mt = doc.add_table(rows=1, cols=4)
    _no_border(mt._tbl)
    for i, (lbl, val) in enumerate([
        ("CLIENT",   meta["client_name"]),
        ("PRODUCT",  meta["product"]),
        ("DEADLINE", meta["deadline"]),
        ("SPOC",     meta["spoc_name"]),
    ]):
        c = mt.cell(0, i)
        _shd(c, C_PURPLE)
        p = c.paragraphs[0]
        p.paragraph_format.space_before = Pt(7)
        p.paragraph_format.space_after  = Pt(2)
        p.paragraph_format.left_indent  = Cm(0.3)
        rl = p.add_run(lbl + "\n")
        rl.font.name = "Calibri"; rl.font.size = Pt(7)
        rl.font.color.rgb = _rgb("CCB8FF")
        rv = p.add_run(val)
        rv.font.name = "Calibri"; rv.font.size = Pt(9)
        rv.font.bold = True; rv.font.color.rgb = _rgb("FFFFFF")
        p2 = c.add_paragraph()
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after  = Pt(7)

    # ── Score + recommendation row ─────────────────────────────────────────────
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    st = doc.add_table(rows=1, cols=2)
    _no_border(st._tbl)
    # Left: score
    sc = st.cell(0, 0)
    _shd(sc, C_LIGHT)
    p = sc.paragraphs[0]
    p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.5)
    r = p.add_run(str(overall_score))
    r.font.name = "Calibri"; r.font.size = Pt(38); r.font.bold = True
    r.font.color.rgb = _rgb(C_PURPLE)
    r2 = p.add_run("/100")
    r2.font.name = "Calibri"; r2.font.size = Pt(13); r2.font.color.rgb = _rgb("AA99CC")
    p2 = sc.add_paragraph()
    p2.paragraph_format.space_before = Pt(0); p2.paragraph_format.space_after = Pt(10)
    p2.paragraph_format.left_indent = Cm(0.5)
    r3 = p2.add_run("OVERALL SCORE")
    r3.font.name = "Calibri"; r3.font.size = Pt(7); r3.font.bold = True
    r3.font.color.rgb = _rgb("8877AA")
    # Right: recommendation
    rc = st.cell(0, 1)
    _shd(rc, C_LIGHT)
    p = rc.paragraphs[0]
    p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.5)
    r = p.add_run(recommendation.upper())
    r.font.name = "Calibri"; r.font.size = Pt(16); r.font.bold = True
    r.font.color.rgb = _rgb(rec_color)
    p2 = rc.add_paragraph()
    p2.paragraph_format.space_before = Pt(0); p2.paragraph_format.space_after = Pt(10)
    p2.paragraph_format.left_indent = Cm(0.5)
    r2 = p2.add_run("RECOMMENDATION")
    r2.font.name = "Calibri"; r2.font.size = Pt(7); r2.font.bold = True
    r2.font.color.rgb = _rgb("8877AA")

    # ── Scorecard table ────────────────────────────────────────────────────────
    _section_heading("QUALIFICATION SCORECARD")
    sc_tbl = doc.add_table(rows=1, cols=4)
    sc_tbl.style = "Table Grid"
    sc_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cols = [("Parameter", 4.2), ("Score", 1.6), ("Evidence (KB)", 8.8), ("Risk Flag", 2.8)]
    for i, (h, _) in enumerate(hdr_cols):
        c = sc_tbl.cell(0, i)
        _shd(c, C_DARK)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
        r = p.add_run(h)
        r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = True
        r.font.color.rgb = _rgb("FFFFFF")

    for idx, param in enumerate(params):
        name     = param.get("parameter", "")
        score    = int(param.get("score", 0))
        evidence = param.get("evidence", "")
        risk     = param.get("risk", "")
        row_bg   = "FFFFFF" if idx % 2 == 0 else "F7F4FF"
        scol = C_GREEN if score >= 8 else (C_ORANGE if score >= 5 else C_RED)

        row = sc_tbl.add_row()
        for ci, (val, align, bold, color, bg) in enumerate([
            (name,                    WD_ALIGN_PARAGRAPH.LEFT,   True,  C_TEXT,                row_bg),
            (f"{score}/10",           WD_ALIGN_PARAGRAPH.CENTER, True,  scol,                  row_bg),
            (evidence,                WD_ALIGN_PARAGRAPH.LEFT,   False, C_TEXT,                row_bg),
            (risk if risk else "—",   WD_ALIGN_PARAGRAPH.LEFT,   False,
             C_ORANGE if risk else "AAAAAA",
             "FFF0E8" if risk else row_bg),
        ]):
            c = row.cells[ci]
            _shd(c, bg)
            p = c.paragraphs[0]
            p.alignment = align
            p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Cm(0.2) if align == WD_ALIGN_PARAGRAPH.LEFT else Cm(0)
            r = p.add_run(str(val))
            r.font.name = "Calibri"; r.font.size = Pt(9); r.font.bold = bold
            r.font.color.rgb = _rgb(color)

    # ── Analysis ───────────────────────────────────────────────────────────────
    _section_heading("ANALYSIS")
    for line in analysis_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(5)
        r = p.add_run(line)
        r.font.name = "Calibri"; r.font.size = Pt(10); r.font.color.rgb = _rgb(C_TEXT)

    # ── Footer ─────────────────────────────────────────────────────────────────
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        f"Generated by iMocha BidBuddy  ·  {datetime.now().strftime('%B %d, %Y')}  ·  Confidential"
    )
    r.font.name = "Calibri"; r.font.size = Pt(8); r.font.italic = True
    r.font.color.rgb = _rgb("CCBBDD")

    # ── Save DOCX ─────────────────────────────────────────────────────────────
    safe = re.sub(r"[^a-z0-9]+", "_", meta["client_name"].lower()).strip("_")
    filename = f"iMocha_{safe}_Deal_Qualification.docx"
    out = dq_dir / filename
    doc.save(out)

    # ── Write internal summary for get_deal_context ────────────────────────────
    risk_rows = [p for p in params if p.get("risk")]
    summary_lines = [
        f"Score: {overall_score}/100  |  Recommendation: {recommendation}",
        f"Parameters scored: {len(params)}",
        f"Risk flags: {len(risk_rows)}",
        "",
        "Scorecard:",
    ] + [
        f"  {p['parameter']}: {p['score']}/10{' ⚠ ' + p['risk'] if p.get('risk') else ''}"
        for p in params
    ] + ["", "Analysis:", analysis_text]
    (dq_dir / "qualification_summary.md").write_text("\n".join(summary_lines))

    # ── Update meta ────────────────────────────────────────────────────────────
    completed = meta.setdefault("stages_completed", [])
    for s in ("analysis", "scorecard"):
        if s not in completed:
            completed.append(s)
    meta["qualification_score"] = overall_score
    meta["stage"] = "rfi"
    _save_meta(deal_id, meta)

    strong_params = [p["parameter"] for p in params if int(p.get("score", 0)) >= 8]
    weak_params   = [p["parameter"] for p in params if int(p.get("score", 0)) < 5 and p.get("risk")]
    return (
        f"Deal Qualification DOCX saved: {filename}\n"
        f"Location: {out}\n"
        f"Score: {overall_score}/100  |  Recommendation: {recommendation}\n"
        f"Parameters scored: {len(params)}  |  Risk flags: {len(risk_rows)}\n"
        f"Strong (≥8): {', '.join(strong_params) or 'none'}\n"
        f"Weak (<5 with risk): {', '.join(weak_params) or 'none'}\n\n"
        f"━━ NEXT STEP — Deal Insights ━━\n"
        f"Based on the scorecard above, now deliver a deal strengths & weaknesses briefing:\n"
        f"  • Top strengths (high-score parameters + client relevance)\n"
        f"  • Key risks / weaknesses (flagged parameters + mitigation)\n"
        f"  • Win strategy (1–2 sentences)\n"
        f"  • Recommended next steps (3–4 actions)\n"
        f"Then call save_deal_insights to persist the analysis."
    )


@mcp.tool()
def list_deal_files(deal_id: str) -> str:
    """Show the full file tree for a deal workspace."""
    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])

    lines = [f"Deal: {deal_id}  ({base})"]
    for folder in ["Deal Qualification", "RFI/Supplier Questionnaire", "RFI/Auto Answer", "RFP"]:
        p = base / folder
        if not p.exists():
            continue
        files = list(p.iterdir())
        lines.append(f"\n  {folder}/")
        for f in sorted(files):
            if f.is_file():
                lines.append(f"    {f.name}  ({f.stat().st_size:,} bytes)")
        if not files:
            lines.append("    (empty)")

    return "\n".join(lines)


# ── Supplier questionnaire ─────────────────────────────────────────────────────

@mcp.tool()
def save_supplier_questionnaire(deal_id: str, questions_json: str) -> str:
    """
    Generate a branded iMocha Clarification Questions XLSX to send TO the client.
    This is NOT an answer document — column 4 ("Client Response") is intentionally
    left blank for the client to fill in.

    PURPOSE: iMocha asks the client for clarifications needed before we can respond
    to their RFP/RFI. The client fills in their responses and returns the file.

    PRODUCT-TYPE AWARE — read meta.product_type and generate questions accordingly:

    TA (Talent Acquisition / Skills Assessment) — focus on:
      - Integration & Technical: ATS systems (Workday Recruiting, Oracle Taleo, Greenhouse,
        iCIMS, SmartRecruiters, SAP SuccessFactors Recruiting), HRMS for employee data, SSO
      - Scope & Delivery: candidate volumes, requisition count, role categories (campus/lateral),
        hiring stages covered (pre-screening, post-shortlist), geographic scope
      - Product Fit: assessment types needed (cognitive, behavioral, SJT, coding, video interview,
        proctoring), competency framework ownership, norm group/benchmark requirements
      - DO NOT ASK about: Skills Taxonomy, Competency Framework build-out, Internal Mobility,
        Career Pathing, Workforce Planning, Succession, Skills Gap Analysis (those are TM topics)

    TM (Talent Management / Skills Intelligence) — focus on:
      - Integration & Technical: HRIS (Workday HCM, SAP SuccessFactors, Oracle HCM), LMS/LXP
        (Cornerstone, Degreed, LinkedIn Learning), Skills Marketplace, Performance Management systems
      - Scope & Delivery: employee headcount, business units in scope, geographies, phased rollout
      - Product Fit: Skills Taxonomy ownership (who maintains it?), Competency Framework maturity,
        use cases (Skills Gap, Career Pathing, Internal Mobility, Succession, Workforce Planning)
      - DO NOT ASK about: ATS integration, Candidate Experience, Proctoring, Coding Assessments,
        hiring volumes, campus recruiting (those are TA topics)

    Both (TA + TM): ask questions from both sets above; clearly label which product each applies to.

    CATEGORIES to use (from RFI_CATEGORIES):
      "Integration & Technical", "Security & Compliance", "Scope & Delivery",
      "Commercial & Legal", "Stakeholder & Governance", "Product Fit"

    Args:
        deal_id:        Client name (e.g. "Accenture")
        questions_json: JSON array — NO answer field, questions only:
                        [{"category": "Integration & Technical", "question": "..."}]
                        Use ONLY the 6 approved category names above.
                        Aim for 3–6 questions per category, 15–30 questions total.
    """
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.drawing.image import Image as XlImage
    except ImportError:
        return "Error: openpyxl not installed."

    try:
        questions = json.loads(questions_json)
    except json.JSONDecodeError as e:
        return f"Error: invalid questions_json — {e}"

    if not isinstance(questions, list) or not questions:
        return "Error: questions_json must be a non-empty JSON array."

    # Strip any stray "answer" fields — this document has no iMocha answers
    for q in questions:
        q.pop("answer", None)

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    sq_dir = base / "RFI" / "Supplier Questionnaire"
    sq_dir.mkdir(parents=True, exist_ok=True)

    product_type = meta.get("product_type", meta.get("product", "TA"))

    # ── BidTrack-matched palette ───────────────────────────────────────────────
    NAVY   = "1B3560"   # matches BidTrack's #1B3560 navy
    BLUE   = "D6E8FF"   # light blue alternating row
    WHITE  = "FFFFFF"
    PURPLE = "491AEB"   # iMocha purple for category divider

    thin_side   = Side(style="thin", color="C5D3E8")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Clarification Questions"

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 65
    ws.column_dimensions["D"].width = 42

    # ── Banner rows 1–3 (navy bg, logo floats above) ─────────────────────────
    for r in range(1, 4):
        ws.row_dimensions[r].height = 28 if r == 1 else 14
        for col in ["A", "B", "C", "D"]:
            cell = ws[f"{col}{r}"]
            cell.fill = PatternFill("solid", fgColor=NAVY)
    ws.merge_cells("A1:D3")

    # ── Embed iMocha logo in banner ──────────────────────────────────────────
    logo_path = TEMPLATES_DIR / "imocha-logo.png"
    if logo_path.exists():
        try:
            img = XlImage(str(logo_path))
            img.width  = 160   # px — keep aspect ratio ~4.66:1 of 937×201
            img.height = 34
            img.anchor = "A1"
            ws.add_image(img)
        except Exception:
            pass  # logo embed failed silently — not critical

    # ── Meta strip (row 4 — repurposed as the "from / for" strip) ───────────
    # Insert an extra row for meta between banner and header
    # We'll use row 4 as a light purple meta strip
    ws.row_dimensions[4].height = 16
    ws.merge_cells("A4:D4")
    c4 = ws["A4"]
    deadline = meta.get("deadline", "TBD")
    spoc     = meta.get("spoc_name", "iMocha Team")
    c4.value = (
        f"  RFI Clarification Questions   ·   {meta['client_name']}   ·   "
        f"Product: {product_type}   ·   Deadline: {deadline}   ·   iMocha SPOC: {spoc}"
    )
    c4.fill = PatternFill("solid", fgColor=PURPLE)
    c4.font = Font(color=WHITE, size=8, italic=True, name="Calibri")
    c4.alignment = Alignment(horizontal="left", vertical="center")

    # ── Column headers (row 5) ────────────────────────────────────────────────
    ws.row_dimensions[5].height = 20
    headers = ["#", "Category", "Clarification Required", "Client Response"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=5, column=ci, value=h)
        c.fill      = PatternFill("solid", fgColor=NAVY)
        c.font      = Font(bold=True, color=WHITE, size=11, name="Calibri")
        c.alignment = Alignment(
            horizontal="center" if ci == 1 else "left",
            vertical="center", wrap_text=True
        )
        c.border = thin_border

    # ── Data rows (start at row 6) ────────────────────────────────────────────
    VALID_CATEGORIES = [
        "Integration & Technical", "Security & Compliance", "Scope & Delivery",
        "Commercial & Legal", "Stakeholder & Governance", "Product Fit",
    ]
    current_row = 6
    current_cat = None
    row_parity  = 0
    categories_seen = []

    for idx, item in enumerate(questions, 1):
        cat = item.get("category", "")
        if not cat or cat not in VALID_CATEGORIES:
            return (
                f"Error: question #{idx} has invalid category '{cat}'.\n"
                f"Valid categories are: {', '.join(VALID_CATEGORIES)}\n"
                f"Fix the category and resubmit."
            )
        question = item.get("question", "").strip()
        if not question:
            continue

        # Category separator row (purple divider, spans all cols)
        if cat != current_cat:
            ws.merge_cells(f"A{current_row}:D{current_row}")
            sep = ws.cell(row=current_row, column=1, value=f"  {cat}")
            sep.fill      = PatternFill("solid", fgColor=PURPLE)
            sep.font      = Font(bold=True, color=WHITE, size=9, name="Calibri")
            sep.alignment = Alignment(horizontal="left", vertical="center")
            sep.border    = thin_border
            ws.row_dimensions[current_row].height = 16
            current_row += 1
            current_cat = cat
            row_parity  = 0
            if cat not in categories_seen:
                categories_seen.append(cat)

        row_bg = WHITE if row_parity % 2 == 0 else BLUE
        row_parity += 1

        # # cell
        n = ws.cell(row=current_row, column=1, value=idx)
        n.fill      = PatternFill("solid", fgColor=row_bg)
        n.font      = Font(bold=True, size=11, name="Calibri")
        n.alignment = Alignment(horizontal="center", vertical="top")
        n.border    = thin_border

        # Category cell
        ccat = ws.cell(row=current_row, column=2, value=cat)
        ccat.fill      = PatternFill("solid", fgColor=row_bg)
        ccat.font      = Font(size=10, name="Calibri")
        ccat.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ccat.border    = thin_border

        # Clarification Required cell
        cq = ws.cell(row=current_row, column=3, value=question)
        cq.fill      = PatternFill("solid", fgColor=row_bg)
        cq.font      = Font(size=11, name="Calibri")
        cq.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        cq.border    = thin_border

        # Client Response cell — intentionally blank (client fills this)
        cr = ws.cell(row=current_row, column=4, value="")
        cr.fill      = PatternFill("solid", fgColor=WHITE)
        cr.font      = Font(size=11, name="Calibri")
        cr.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        cr.border    = thin_border

        est_lines = max(1, len(question) // 60)
        ws.row_dimensions[current_row].height = min(15 * est_lines + 5, 100)
        current_row += 1

    # Freeze pane below header (row 5), enable filter from row 5
    ws.freeze_panes = "A6"
    ws.auto_filter.ref = f"A5:D{current_row - 1}"

    safe     = re.sub(r"[^a-z0-9]+", "_", meta["client_name"].lower()).strip("_")
    filename = f"iMocha_{safe}_RFI_Clarification_Questions.xlsx"
    out      = sq_dir / filename
    wb.save(out)

    # Write summary for get_deal_context
    summary = (
        f"RFI Clarification Questions: {filename}\n"
        f"Questions: {len(questions)}  |  Categories: {', '.join(categories_seen)}\n"
        f"Product type: {product_type}\n"
        f"Status: Sent to client for response — awaiting replies.\n"
    )
    (sq_dir / "questionnaire_summary.md").write_text(summary)

    completed = meta.setdefault("stages_completed", [])
    if "supplier_questionnaire" not in completed:
        completed.append("supplier_questionnaire")
    _save_meta(deal_id, meta)

    return (
        f"RFI Clarification Questions saved: {filename}\n"
        f"Location: {out}\n"
        f"Questions: {len(questions)}  |  Categories: {', '.join(categories_seen)}\n"
        f"Product scope: {product_type}\n"
        f"Column D ('Client Response') is blank — send this file to the client to fill in."
    )


# ── RFP ingestion ──────────────────────────────────────────────────────────────

@mcp.tool()
def ingest_rfp(deal_id: str, pdf_path: str) -> str:
    """
    Copy the RFP PDF into Deal Qualification/ and extract its text for Claude to read.
    Returns the full extracted text so Claude can immediately start working with it.

    Args:
        deal_id:  Client name (e.g. "Accenture")
        pdf_path: Full path to the RFP PDF on disk
    """
    src = Path(pdf_path)
    if not src.exists():
        return f"Error: file not found at {pdf_path}"

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    dq_folder = base / "Deal Qualification"
    dq_folder.mkdir(parents=True, exist_ok=True)

    dest = dq_folder / "rfp.pdf"
    shutil.copy2(src, dest)

    try:
        from pypdf import PdfReader
    except ImportError:
        return "Error: pypdf not installed. Run: pip install pypdf"

    try:
        reader = PdfReader(dest)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"--- Page {i + 1} ---\n{text}")
        full_text = "\n\n".join(pages)
    except Exception as e:
        return f"Error extracting PDF: {e}"

    text_file = dq_folder / "rfp_text.txt"
    text_file.write_text(full_text)

    # Auto-classify product type from RFP text
    classification = _classify_product(full_text)
    product_type = classification["product_type"]

    # Update meta
    meta["rfp_filename"] = src.name
    meta["rfp_pages"] = len(reader.pages)
    meta["product_type"] = product_type
    meta["product_ta_signals"] = classification["ta_hits"]
    meta["product_tm_signals"] = classification["tm_hits"]
    _save_meta(deal_id, meta)

    preview = full_text[:40_000]
    truncated = len(full_text) > 40_000

    # Build classification summary line
    if product_type == "unknown":
        cls_line = "⚠️  Product: UNKNOWN — no TA or TM signals found. Ask the analyst to clarify."
    else:
        cls_line = (
            f"✅ Auto-detected product: {product_type}  "
            f"(TA signals: {len(classification['ta_hits'])}, TM signals: {len(classification['tm_hits'])})"
        )

    return (
        f"RFP loaded: {src.name}  ({len(reader.pages)} pages, {len(full_text):,} chars)\n"
        f"Saved to: {dest}\n"
        f"{cls_line}\n"
        + (f"[First 40k chars shown — full text in rfp_text.txt]\n" if truncated else "")
        + f"\n{preview}"
    )


@mcp.tool()
def classify_deal(deal_id: str, text: str = "") -> str:
    """
    Auto-detect whether this deal is TA, TM, or Both by scanning keyword signals.
    Call this after ingesting an RFP, or pass raw text directly.
    Saves result to meta.json so all downstream tools (proposal, docs) use it automatically.

    Args:
        deal_id: Client name (e.g. "Accenture")
        text:    Optional — raw text to classify. If empty, reads rfp_text.txt from the deal folder.
    """
    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])

    if not text.strip():
        txt_path = base / "Deal Qualification" / "rfp_text.txt"
        if not txt_path.exists():
            return "Error: no rfp_text.txt found and no text provided. Ingest an RFP first or pass text directly."
        text = txt_path.read_text()

    classification = _classify_product(text)
    product_type = classification["product_type"]

    meta["product_type"] = product_type
    meta["product_ta_signals"] = classification["ta_hits"]
    meta["product_tm_signals"] = classification["tm_hits"]
    _save_meta(deal_id, meta)

    ta_hits = classification["ta_hits"]
    tm_hits = classification["tm_hits"]

    lines = [f"Product classification for {deal_id}: **{product_type}**"]
    lines.append(f"TA signals ({len(ta_hits)}): {', '.join(ta_hits) if ta_hits else 'none'}")
    lines.append(f"TM signals ({len(tm_hits)}): {', '.join(tm_hits) if tm_hits else 'none'}")

    if product_type == "unknown":
        lines.append(
            "\n⚠️  No TA or TM signals found. Ask the analyst: is this deal about "
            "hiring/candidates (TA) or employee skills/development (TM)?"
        )
    elif product_type == "Both":
        lines.append(
            "\n📋 Both TA and TM signals detected. "
            "Confirm with the analyst which product(s) to lead with in the proposal."
        )

    return "\n".join(lines)


# ── RFI tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def parse_rfi_xlsx(deal_id: str, xlsx_path: str) -> str:
    """
    STEP 1 OF AUTO-ANSWER FLOW — Load the client's RFI questionnaire XLSX.

    Copies the original file to RFI/Auto Answer/rfi_original.xlsx (ORIGINAL IS NEVER MODIFIED).
    Returns a full HITL structure preview so the user can confirm before answering begins.

    The output shows:
      - Sheet names with scored column detection (Question / Answer / Status / Context)
      - ALL questions with row numbers and any context column values inline
      - Confirmation checklist before fill_rfi_xlsx is called

    Column types detected (scored, not just first-keyword-match):
      - Question col:  column containing the vendor's questions/requirements
      - Answer col:    column where iMocha writes responses
      - Status col:    optional — for "Supported / Partial / Review Required" badges
      - Context cols:  optional — columns like Section/Category read per row to help Claude answer

    After the user reviews and confirms the structure, call fill_rfi_xlsx with:
      - answers_json with answer + confidence per row
      - answer_col and optionally status_col

    IMPORTANT: The original file at xlsx_path is NEVER touched. fill_rfi_xlsx writes
    a duplicate (rfi_filled.xlsx) preserving all original formatting, colors, and structure.

    Args:
        deal_id:    Client name (e.g. "Accenture")
        xlsx_path:  Full path to the client's RFI XLSX file on disk
    """
    try:
        import openpyxl
    except ImportError:
        return "Error: openpyxl not installed. Run: pip install openpyxl"

    src = Path(xlsx_path)
    if not src.exists():
        return f"Error: file not found at {xlsx_path}"

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    dest_folder = base / "RFI" / "Auto Answer"
    dest_folder.mkdir(parents=True, exist_ok=True)

    # Copy original — this file is NEVER modified
    original_dest = dest_folder / f"rfi_original{src.suffix}"
    if src.resolve() != original_dest.resolve():
        shutil.copy2(src, original_dest)

    from openpyxl.cell.cell import MergedCell as _MergedCell
    wb = openpyxl.load_workbook(original_dest, data_only=True)

    # ── Customer rules from Instructions sheet ─────────────────────────────────
    _SKIP_SHEETS = {"Instructions", "Dropdowns"}
    instructions_rules = []
    if "Instructions" in wb.sheetnames:
        for _irow in wb["Instructions"].iter_rows(values_only=True):
            for _iv in _irow:
                if _iv and isinstance(_iv, str) and len(_iv.strip()) > 15:
                    instructions_rules.append(_iv.strip())

    def _get_fill_type(sname: str, ws) -> dict:
        """Return fill_type + constraints dict for a sheet."""
        if sname in _SKIP_SHEETS:
            return {"fill_type": "skip"}
        nl = sname.lower()
        if "pricing" in nl:
            return {"fill_type": "pricing_table"}
        if "contact" in nl:
            return {"fill_type": "contact_form"}
        if "reference" in nl:
            return {"fill_type": "reference_form"}
        import re as _re_ft
        char_limit = None
        dropdown_vals: list = []
        for dv in ws.data_validations.dataValidation:
            if dv.type == "textLength" and dv.formula1:
                try:
                    char_limit = int(dv.formula1)
                except (ValueError, TypeError):
                    pass
            elif dv.type == "list" and dv.formula1:
                f1 = str(dv.formula1)
                if f1.startswith('"'):
                    dropdown_vals = [v.strip() for v in f1.strip('"').split(',') if v.strip()]
        # Also scan column headers and first few rows for plain-text limit mentions
        # e.g. "Max 600 characters", "Limit: 250 words", "(max 500 chars)"
        if not char_limit:
            _CHAR_PAT  = _re_ft.compile(r'(?:max(?:imum)?|limit)[:\s]*(\d+)\s*char', _re_ft.IGNORECASE)
            _WORD_PAT  = _re_ft.compile(r'(?:max(?:imum)?|limit)[:\s]*(\d+)\s*word',  _re_ft.IGNORECASE)
            _PAREN_PAT = _re_ft.compile(r'\((?:max|limit)[:\s]*(\d+)\s*(?:char|word)',  _re_ft.IGNORECASE)
            for _row in ws.iter_rows(max_row=5, values_only=True):
                for _cell in _row:
                    if not _cell or not isinstance(_cell, str):
                        continue
                    for pat in (_CHAR_PAT, _PAREN_PAT):
                        m = pat.search(_cell)
                        if m:
                            char_limit = int(m.group(1))
                            break
                    if char_limit:
                        break
                if char_limit:
                    break
        # 0-4 scoring pattern in cell content
        for _drow in ws.iter_rows(max_row=20, values_only=True):
            for _dc in _drow:
                if _dc and isinstance(_dc, str) and "0,1,2,3,4" in _dc:
                    return {"fill_type": "numeric_score", "valid_values": ["0","1","2","3","4"]}
        # Pull dropdown values from the Dropdowns sheet if not found inline
        if not dropdown_vals and "Dropdowns" in wb.sheetnames:
            for _ddr in wb["Dropdowns"].iter_rows(min_row=2, values_only=True):
                _ddv = _ddr[0] if _ddr else None
                if _ddv and str(_ddv).strip():
                    dropdown_vals.append(str(_ddv).strip())
        result: dict = {"fill_type": "qa_freetext"}
        if char_limit:
            result["char_limit"] = char_limit
        if dropdown_vals:
            result["valid_values"] = dropdown_vals
        return result

    # ── Column signal sets for scored detection ────────────────────────────────
    Q_SIGNALS      = ["question", "requirement", "description", "ask", "query", "item",
                      "criteria", "criterion", "area", "topic", "specification", "parameter", "text"]
    A_SIGNALS      = ["answer", "response", "vendor", "reply", "comment", "supplier",
                      "fill", "input", "your", "remarks", "imocha"]
    STATUS_SIGNALS = ["status", "support", "supported", "capability", "compliance",
                      "coverage", "available", "availability", "met", "provided"]
    CONTEXT_SIGNALS= ["section", "category", "sub", "ref", "reference", "no.", "sr.",
                      "group", "domain", "module", "theme", "type", "number", "id"]

    def _col_score(header, signals):
        h = header.lower()
        return sum(1 for s in signals if s in h)

    def _detect_cols(hdr):
        """Score each header against all four signal sets; pick best per role."""
        q_s = [_col_score(h, Q_SIGNALS)      for h in hdr]
        a_s = [_col_score(h, A_SIGNALS)      for h in hdr]
        st_s= [_col_score(h, STATUS_SIGNALS) for h in hdr]
        cx_s= [_col_score(h, CONTEXT_SIGNALS)for h in hdr]

        def _best(scores, exclude=()):
            pairs = [(s, i) for i, s in enumerate(scores) if i not in exclude]
            best = max(pairs, key=lambda x: x[0], default=(0, None))
            return best[1] if best[0] > 0 else None

        q_col      = _best(q_s)
        q_certain  = q_col is not None
        if q_col is None:
            q_col = max(range(len(hdr)), key=lambda i: len(hdr[i]), default=0) if hdr else 0
        a_col      = _best(a_s, exclude=(q_col,))
        a_certain  = a_col is not None
        if a_col is None:
            a_col = max((i for i, c in enumerate(hdr) if c and i != q_col), default=(q_col + 1 if q_col is not None else 1))
        st_col = _best(st_s, exclude=(q_col, a_col))
        assigned = {c for c in (q_col, a_col, st_col) if c is not None}
        q_runners = [i for i, s in enumerate(q_s) if s > 0 and i not in assigned]
        cx_direct = [i for i, s in enumerate(cx_s) if s > 0 and i not in assigned and i not in q_runners]
        cx_cols = q_runners + cx_direct
        confident = q_certain and a_certain
        return q_col, a_col, st_col, cx_cols, confident

    def _col_letter(idx):
        if idx is None:
            return "?"
        n = idx + 1
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    # ── Build structure — merge-aware ─────────────────────────────────────────
    col_map_to_save: dict = {}
    structure = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]

        wide_merge_rows = set()
        for mr in ws.merged_cells.ranges:
            if (mr.max_col - mr.min_col) >= 2:
                for r in range(mr.min_row, mr.max_row + 1):
                    wide_merge_rows.add(r)

        rows_data = []
        for row_idx, row in enumerate(ws.iter_rows(), start=1):
            cells = []
            for cell in row:
                if isinstance(cell, _MergedCell):
                    cells.append("")
                else:
                    cells.append(str(cell.value).strip() if cell.value is not None else "")

            if not any(c for c in cells):
                continue

            rows_data.append({
                "row": row_idx,
                "cells": cells,
                "is_category_header": row_idx in wide_merge_rows,
            })

        if rows_data:
            structure[sheet_name] = rows_data

    (dest_folder / "rfi_structure.json").write_text(json.dumps(structure, indent=2))

    # ── Build HITL preview ────────────────────────────────────────────────────
    lines = [
        "═" * 70,
        f"AUTO-ANSWER STEP 1 — Structure Preview: {src.name}",
        f"Original saved to: {original_dest}  (WILL NOT BE MODIFIED)",
        "═" * 70,
        f"Sheets ({len(wb.sheetnames)}): {', '.join(wb.sheetnames)}",
        "",
    ]

    # Show customer rules extracted from Instructions sheet
    if instructions_rules:
        lines.append("⚠  CUSTOMER RULES (from Instructions sheet — must be followed):")
        for rule in instructions_rules[:12]:
            lines.append(f"   • {rule[:120]}")
        lines.append("")

    total_questions = 0
    # track per-sheet answerable rows for the params block
    sheet_answerable: dict = {}
    sheet_col_map: dict = {}

    for sheet_name, rows_data in structure.items():
        if not rows_data:
            continue

        question_rows = [r for r in rows_data if not r["is_category_header"]]
        category_rows = [r for r in rows_data if r["is_category_header"]]

        lines.append(f"┌─ Sheet: '{sheet_name}'  ({len(rows_data)} non-empty rows, "
                     f"{len(category_rows)} banner rows, {len(question_rows)} data rows)")

        header_row = next(
            (r for r in question_rows if sum(1 for c in r["cells"] if c) >= 2),
            question_rows[0] if question_rows else None,
        )
        if not header_row:
            lines.append("│  (no data rows found)")
            lines.append("└─")
            continue

        hdr = header_row["cells"]
        lines.append(f"│  Row {header_row['row']} (COLUMN HEADERS): {[c for c in hdr if c]}")

        q_col, a_col, st_col, cx_cols, confident = _detect_cols(hdr)
        sheet_col_map[sheet_name] = (q_col, a_col, st_col, cx_cols, confident)

        # Sheet-type (for answering guidance) and fill-type (for constraints)
        section_names = [
            next((c for c in r["cells"] if c), "")
            for r in rows_data if r["is_category_header"]
        ]
        stype = _detect_sheet_type(sheet_name, hdr, section_names)
        sheet_col_map[sheet_name] = (q_col, a_col, st_col, cx_cols, confident, stype)
        type_label = _SHEET_TYPE_LABELS.get(stype, stype)

        ws_live = wb[sheet_name]
        ft_info = _get_fill_type(sheet_name, ws_live)
        fill_type    = ft_info.get("fill_type", "qa_freetext")
        char_limit   = ft_info.get("char_limit")
        valid_values = ft_info.get("valid_values")
        a_letter     = _col_letter(a_col) if a_col is not None else "B"
        ft_info["answer_col_letter"] = a_letter
        col_map_to_save[sheet_name] = ft_info

        # Non-fillable sheets: show a brief banner and skip question listing
        _FT_SKIP_LABELS = {
            "skip":          "⏩ SKIP — read-only (Instructions / Dropdowns source)",
            "pricing_table": "💰 PRICING TABLE — fill manually (numeric/multi-column)",
            "contact_form":  "📋 CONTACT FORM — fill manually (label→value rows)",
            "reference_form":"📋 REFERENCE FORM — fill manually (label→value rows)",
        }
        if fill_type in _FT_SKIP_LABELS:
            lines.append(f"│  {_FT_SKIP_LABELS[fill_type]}")
            lines.append(f"└─ 0 fill-target rows (skipped by fill engine)")
            lines.append("")
            sheet_answerable[sheet_name] = []
            continue

        lines.append("│")
        lines.append(f"│  ── Sheet type: {type_label} ──")
        # Constraint banner
        if fill_type == "numeric_score":
            lines.append(f"│  ⚠ NUMERIC SCORE SHEET — answers must be one of: {valid_values}")
            lines.append(f"│    Write the digit only (0=Not Supported … 4=Fully Supported)")
        elif fill_type == "qa_freetext":
            if char_limit:
                lines.append(f"│  ⚠ {char_limit}-CHARACTER LIMIT per cell — YOU must write within this limit.")
                lines.append(f"│    Condense your answer to fit while keeping all key points and intent.")
                lines.append(f"│    Do NOT rely on auto-trim — a hard cut destroys meaning.")
            if valid_values:
                lines.append(f"│  ⚠ VALID VALUES: {valid_values}  (dropdown — use exact casing)")
        lines.append("│")
        conf_badge = "✅ auto-detected" if confident else "⚠️  low confidence — please verify"
        lines.append(f"│  ── Column detection ({conf_badge}) ──")
        lines.append(f"│  Questions to READ   → col {_col_letter(q_col)}  \"{hdr[q_col] if q_col is not None and q_col < len(hdr) else '?'}\"{'  ✅' if confident else '  ⚠️ guessed'}")
        lines.append(f"│  Response to WRITE   → col {a_letter}  \"{hdr[a_col] if a_col is not None and a_col < len(hdr) else 'empty — will be created'}\"{'  ✅' if confident else '  ⚠️ guessed'}")
        if st_col is not None:
            lines.append(f"│  YES/NO/NA Status    → col {_col_letter(st_col)}  \"{hdr[st_col] if st_col < len(hdr) else '?'}\"  ✅")
        else:
            lines.append(f"│  YES/NO/NA Status    → not detected  ← tell me the column letter, or omit")
        if cx_cols:
            cx_names = [f"col {_col_letter(i)} \"{hdr[i]}\"" for i in cx_cols if i < len(hdr)]
            lines.append(f"│  Context / Detail    → {', '.join(cx_names)}  ← read per row to help answering")
        else:
            lines.append(f"│  Context / Detail    → none detected  ← tell me if there is one")
        lines.append("│")
        lines.append("│  ── Questions (FILL THESE ROWS) ──")

        hdr_row_num = header_row["row"]
        current_cat = ""
        answerable_rows = []

        for r in rows_data:
            if r["row"] == hdr_row_num:
                continue
            if r["is_category_header"]:
                cat_text = next((c for c in r["cells"] if c), "").strip()
                current_cat = cat_text
                lines.append(f"│")
                lines.append(f"│  ▸ SECTION: {cat_text}  (row {r['row']} — banner, DO NOT FILL)")
            else:
                q_text = r["cells"][q_col] if q_col is not None and q_col < len(r["cells"]) else ""
                if q_text and len(q_text) > 3:
                    total_questions += 1
                    answerable_rows.append(r["row"])
                    q_preview = q_text[:55] + ("…" if len(q_text) > 55 else "")
                    ctx_parts = []
                    for i in cx_cols:
                        if i < len(r["cells"]) and r["cells"][i]:
                            ctx_parts.append(r["cells"][i][:50])
                    ctx_str = f"  ↳ {' | '.join(ctx_parts)}" if ctx_parts else ""
                    lines.append(f"│  ✎ Row {r['row']:>3}  [{current_cat}]  {q_preview}{ctx_str}")

        sheet_answerable[sheet_name] = answerable_rows
        skip_rows = [r["row"] for r in rows_data if r["is_category_header"]]
        lines.append(f"│")
        lines.append(f"└─ {len(answerable_rows)} fill-target rows  |  {len(skip_rows)} banner rows (skipped automatically)")
        lines.append("")

    # ── Save per-sheet column map for fill_rfi_xlsx ──────────────────────────
    (dest_folder / "rfi_col_map.json").write_text(json.dumps(col_map_to_save, indent=2))

    # ── Parameters block ──────────────────────────────────────────────────────
    answerable_flat = {sn: rows for sn, rows in sheet_answerable.items() if rows}
    fillable_sheets = {sn: v for sn, v in sheet_col_map.items()
                       if col_map_to_save.get(sn, {}).get("fill_type") == "qa_freetext"
                       or col_map_to_save.get(sn, {}).get("fill_type") == "numeric_score"}
    any_uncertain = not all(v[4] for v in fillable_sheets.values()) if fillable_sheets else False

    lines += ["═" * 70, f"TOTAL FILL-TARGET QUESTIONS: {total_questions}", ""]

    if any_uncertain:
        lines += [
            "⚠️  COLUMN DETECTION WAS UNCERTAIN FOR ONE OR MORE SHEETS.",
            "   Please confirm or correct each column before I proceed.",
            "   Reply with the correct letters, e.g.:",
            "     Q=C   A=E   Status=F   Context=D",
            "   (use the column letters shown in your spreadsheet — A, B, C...)",
            "",
        ]
    else:
        lines.append("✅  Columns detected with confidence. Please confirm before I proceed.")
        lines.append("")

    lines.append("  Per-sheet answer column mapping (auto-saved to rfi_col_map.json):")
    for sn, ft in col_map_to_save.items():
        ft_label = ft.get("fill_type", "?")
        a_let = ft.get("answer_col_letter", "?")
        extras = []
        if ft.get("char_limit"):
            extras.append(f"limit={ft['char_limit']}chars")
        if ft.get("valid_values"):
            extras.append(f"values={ft['valid_values']}")
        extras_str = f"  [{', '.join(extras)}]" if extras else ""
        lines.append(f"    \"{sn}\"  →  fill_type={ft_label}  answer_col={a_let}{extras_str}")
    lines += [
        "",
        "  To override a column, reply:",
        "    Q=<letter>  A=<letter>  Status=<letter>  Context=<letter>",
        "  Example:  Q=C  A=E  Status=F  Context=D",
        "",
        "  FILL-TARGET ROW NUMBERS (answer ONLY these rows):",
    ]
    for sn, rows in answerable_flat.items():
        row_str = ", ".join(str(r) for r in rows)
        lines.append(f"    Sheet \"{sn}\": {row_str}")
    lines.append("")

    # ── Answering guidance per detected sheet type ─────────────────────────────
    detected_types = list({v[5] for v in sheet_col_map.values()})
    if detected_types:
        lines.append("─" * 70)
        lines.append("ANSWERING GUIDANCE (read before calling fill_rfi_xlsx):")
        lines.append("")
        for stype in detected_types:
            lines.append(_SHEET_TYPE_GUIDANCE.get(stype, _SHEET_TYPE_GUIDANCE["general_rfi"]))
            lines.append("")
        lines.append("─" * 70)

    lines += [
        "",
        "  The banner/section rows listed above are NOT fill targets.",
        "  Once you confirm the mapping, load the recommended KB files, then answer",
        "  each question and call fill_rfi_xlsx.",
        "═" * 70,
    ]
    return "\n".join(lines)


@mcp.tool()
def fill_rfi_xlsx(
    deal_id: str,
    answers_json: str,
    answer_col: str = "C",
    status_col: str = "",
    sheet_type: str = "general_rfi",
) -> str:
    """
    STEP 2 OF AUTO-ANSWER FLOW — Write iMocha's answers into the client's RFI XLSX.

    PREREQUISITES:
      - parse_rfi_xlsx must have run first (original saved as rfi_original.xlsx)
      - User must have confirmed the structure from parse_rfi_xlsx output

    HOW IT WORKS:
      1. Copies rfi_original to rfi_filled.xlsx — ALL original formatting preserved
      2. Writes answers into answer_col
      3. If status_col is set, writes a colour-coded status badge:
           confidence "high"   → "Supported"        (green)
           confidence "medium" → "Partial"           (amber)
           confidence "low"    → "Review Required"   (red)
      4. Never modifies the original file

    ══════════════════════════════════════════════════════════════
    ANSWERING MODE — KB SOURCED, FULLY SYNTHESISED
    ══════════════════════════════════════════════════════════════
    Every answer must be faithfully sourced from the project KB files.
    Cross-section synthesis is required — pull any proof point (named
    features, customer references, SLA figures, integration details,
    demo/video links) from ANY KB section where it is relevant to the
    question, not only from the section whose heading matches.

    ANSWER DEPTH & STRUCTURE — write at sales-consultant quality:
      • Open with a direct stance: Yes / Partial / No.
      • Use named bullet sub-sections where the topic has multiple facets.
      • Include specific iMocha feature names (Tara, iMocha Projects,
        Assessment Agent, Skill Inference Engine) when they apply.
      • Include customer proof points (Capgemini, Deloitte, UN agencies,
        L'Oréal, Philip Morris) when they substantiate a claim.
      • Include concrete numbers (SLA %, RTO, RPO, skills count, language
        count) when present in KB.
      • Include demo/video links and document references when KB lists them.
      • Use first person ("iMocha supports…", "We provide…").

    Confidence rules:
      "high"   — KB directly and specifically covers this question.
      "medium" — KB partially covers it; write the best available answer
                 and signal uncertainty via the status badge — NOT via
                 [CONFIRM] text in the answer cell.
      "low"    — KB is completely silent on this topic; write
                 [CONFIRM: <what to look up>] ONLY for genuinely absent
                 topics (e.g. commercial pricing, TBD placeholders,
                 scope-specific items). Never use [CONFIRM] for product
                 capabilities the KB covers, even partially.
    ══════════════════════════════════════════════════════════════

    Args:
        deal_id:      Client name (e.g. "Accenture")
        answers_json: JSON array — one entry per question row:
                      [
                        {"sheet": "Sheet1", "row": 2,
                         "answer": "iMocha supports...",
                         "confidence": "high"},
                        {"sheet": "Sheet1", "row": 3,
                         "answer": "iMocha partially covers this via...",
                         "confidence": "medium"},
                        {"sheet": "Sheet1", "row": 4,
                         "answer": "[CONFIRM: verify SSO protocol in security KB]",
                         "confidence": "low"}
                      ]
                      confidence: "high" | "medium" | "low"  (default "high" if omitted)
        answer_col:   Excel column letter for answers (e.g. "C", "D"). Default "C".
        status_col:   Excel column letter for status badge (e.g. "D", "E").
                      Leave empty to skip status column entirely.
        sheet_type:   Sheet type from parse_rfi_xlsx detection — controls CONFIRM tag prefix
                      for low-confidence answers. One of:
                        "general_rfi" (default) → [CONFIRM: <detail>]
                        "risk_assessment"        → [CONFIRM:CONTRACTUAL — <detail>]
                        "ai_security"            → [CONFIRM:AI-GOVERNANCE — <detail>]
                        "data_privacy"           → [CONFIRM:LEGAL — <detail>]
                        "compliance"             → [CONFIRM:COMPLIANCE — <detail>]
                        "security"               → [CONFIRM:SECURITY — <detail>]
                        "technical_spec"         → [CONFIRM:TECHNICAL — <detail>]
    """
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return "Error: openpyxl not installed."

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    auto_answer_dir = base / "RFI" / "Auto Answer"

    originals = list(auto_answer_dir.glob("rfi_original*"))
    if not originals:
        return "Error: no original RFI file found. Run parse_rfi_xlsx first."

    # Load per-sheet column map saved by parse_rfi_xlsx
    col_map_path = auto_answer_dir / "rfi_col_map.json"
    col_map: dict = json.loads(col_map_path.read_text()) if col_map_path.exists() else {}

    try:
        answers = json.loads(answers_json)
    except json.JSONDecodeError as e:
        return f"Error: invalid answers_json — {e}"

    if not isinstance(answers, list):
        return "Error: answers_json must be a JSON array."

    def _col_num(letter):
        letter = letter.upper().strip()
        return sum((ord(ch) - 64) * (26 ** i) for i, ch in enumerate(reversed(letter)))

    default_answer_col_num = _col_num(answer_col)
    status_col_num = _col_num(status_col) if status_col.strip() else None

    STATUS_MAP = {"high": "Supported", "medium": "Partial", "low": "Review Required"}

    # Prefix for low-confidence CONFIRM tags — varies by sheet type
    _CONFIRM_PREFIX = {
        "risk_assessment": "CONFIRM:CONTRACTUAL",
        "ai_security":     "CONFIRM:AI-GOVERNANCE",
        "data_privacy":    "CONFIRM:LEGAL",
        "compliance":      "CONFIRM:COMPLIANCE",
        "security":        "CONFIRM:SECURITY",
        "technical_spec":  "CONFIRM:TECHNICAL",
        "general_rfi":     "CONFIRM",
    }
    confirm_tag = _CONFIRM_PREFIX.get(sheet_type.strip().lower(), "CONFIRM")

    # ── Initialise rfi_filled — copy original only on first call ─────────────
    # Subsequent calls patch the existing rfi_filled.xlsx so answers accumulate
    # across multiple fill_rfi_xlsx calls (one per sheet group).
    original = originals[0]
    out = auto_answer_dir / "rfi_filled.xlsx"
    if not out.exists():
        shutil.copy2(original, out)

    import re as _re
    import zipfile as _zf
    from io import BytesIO as _BytesIO

    filled = high_count = medium_count = low_count = skipped = merged_skipped = 0
    truncated_count = invalid_val_count = 0
    sheet_counts = {}
    over_limit_report: list[str] = []  # rows rejected for exceeding char limit

    def _col_letter(n: int) -> str:
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    def _col_num_from_letters(letters: str) -> int:
        n = 0
        for ch in letters.upper():
            n = n * 26 + ord(ch) - 64
        return n

    def _xml_esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _inline_cell(ref: str, val: str) -> str:
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_xml_esc(val)}</t></is></c>'

    stat_letter = _col_letter(status_col_num) if status_col_num is not None else None

    # Group answers by sheet, keyed by row number
    updates_by_sheet: dict = {}
    audit_rows: list = []  # for answers.md
    for item in answers:
        sheet_name = item.get("sheet", "")
        row = item.get("row")
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        kb_source = str(item.get("kb_source", "")).strip()
        confidence = str(item.get("confidence", "high")).lower()
        if confidence not in STATUS_MAP:
            confidence = "high"
        if not sheet_name or not isinstance(row, int) or row < 1:
            skipped += 1
            continue
        # For low-confidence answers, enforce sheet-type-specific CONFIRM tag prefix
        if confidence == "low" and answer and not answer.startswith("["):
            answer = f"[{confirm_tag} — {answer}]"
        updates_by_sheet.setdefault(sheet_name, {})[row] = {
            "answer": answer, "confidence": confidence
        }
        audit_rows.append({
            "sheet": sheet_name, "row": row, "question": question,
            "answer": answer, "confidence": confidence, "kb_source": kb_source,
        })

    def _patch_ws(ws_xml: str, by_row: dict, a_col_num: int, a_col_letter: str,
                  s_col_num=None, s_col_letter=None) -> str:
        """Surgically insert/replace only the answer and optional status cells in each
        targeted row, leaving all other XML — styles, merges, formulas, images —
        completely untouched."""

        def patch_row_match(m: _re.Match) -> str:
            row_xml = m.group(0)
            rn_m = _re.search(r'<row\b[^>]*\br="(\d+)"', row_xml)
            if not rn_m or int(rn_m.group(1)) not in by_row:
                return row_xml
            rn = int(rn_m.group(1))
            u = by_row[rn]

            # Find end of opening <row …> tag
            tag_end = row_xml.index(">") + 1
            is_self_closing = row_xml[:tag_end].rstrip().endswith("/>")
            interior = "" if is_self_closing else row_xml[tag_end:-len("</row>")]

            # Parse existing cells: col_num → xml fragment
            cell_pat = _re.compile(
                r'<c\s[^>]*r="([A-Z]+)\d+"[^>]*>.*?</c>|<c\s[^>]*/>',
                _re.DOTALL,
            )
            cells: dict = {}
            for cm in cell_pat.finditer(interior):
                letters_m = _re.search(r'r="([A-Z]+)\d+"', cm.group(0))
                if letters_m:
                    cells[_col_num_from_letters(letters_m.group(1))] = cm.group(0)

            # Write answer cell
            cells[a_col_num] = _inline_cell(f"{a_col_letter}{rn}", u["answer"])
            # Write status cell only when explicitly requested
            if s_col_num is not None and s_col_letter:
                cells[s_col_num] = _inline_cell(
                    f"{s_col_letter}{rn}", STATUS_MAP[u["confidence"]]
                )

            # Reconstruct row in column order
            open_tag = row_xml[:tag_end].rstrip()
            if open_tag.endswith("/>"):
                open_tag = open_tag[:-2] + ">"
            return open_tag + "".join(cells[k] for k in sorted(cells)) + "</row>"

        return _re.sub(r"<row\b[^>]*>.*?</row>|<row\b[^>]*/?>", patch_row_match, ws_xml, flags=_re.DOTALL)

    # Parse workbook.xml to build sheet name → worksheet file path map
    # Use attribute-order-independent matching (XML spec allows any order)
    buf = _BytesIO()
    with _zf.ZipFile(out, "r") as zin:
        wb_xml   = zin.read("xl/workbook.xml").decode("utf-8")
        rels_xml = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        sheet_rid: dict = {}
        for _stag in _re.finditer(r'<sheet\b([^>]*)/?>', wb_xml):
            _attrs = _stag.group(1)
            _nm = _re.search(r'\bname="([^"]+)"', _attrs)
            _ri = _re.search(r'\br:id="([^"]+)"', _attrs)
            if _nm and _ri:
                sheet_rid[_nm.group(1)] = _ri.group(1)
        rid_target = dict(_re.findall(r'<Relationship\b[^>]*\bId="([^"]+)"[^>]*\bTarget="([^"]+)"', rels_xml))
        sheet_file: dict = {}
        for name, rid in sheet_rid.items():
            target = rid_target.get(rid, "")
            if target.startswith("worksheets/"):
                sheet_file[name] = f"xl/{target}"

        # Patch only the worksheets that have answers, applying per-sheet rules
        modified: dict = {}
        for sheet_name, by_row in updates_by_sheet.items():
            if sheet_name not in sheet_file:
                skipped += len(by_row)
                continue

            # Per-sheet constraints from col_map
            sheet_meta   = col_map.get(sheet_name, {})
            fill_type    = sheet_meta.get("fill_type", "qa_freetext")
            char_limit   = sheet_meta.get("char_limit")
            valid_values = sheet_meta.get("valid_values")

            # Skip read-only / manual sheets
            if fill_type in ("skip", "pricing_table", "contact_form", "reference_form"):
                skipped += len(by_row)
                continue

            # Explicit answer_col parameter always wins over auto-detected col_map
            raw_a_letter = answer_col.upper().strip()
            sheet_a_num  = _col_num(raw_a_letter)
            sheet_a_letter = _col_letter(sheet_a_num)

            # Status column: only write for free-text sheets (not numeric/dropdown)
            write_status  = (fill_type == "qa_freetext") and (status_col_num is not None)
            eff_s_num     = status_col_num if write_status else None
            eff_s_letter  = stat_letter    if write_status else None

            # Apply constraints to every answer in this sheet before patching
            for rn, u in by_row.items():
                ans = u["answer"]
                # Char limit enforcement: reject oversized answers rather than silently cutting them.
                # A hard cut destroys meaning; the caller must re-submit a condensed answer.
                if char_limit and len(ans) > char_limit:
                    u["_over_limit"] = len(ans)
                    truncated_count += 1
                    over_limit_report.append(
                        f"  • Sheet '{sheet_name}' row {rn}: {len(ans)} chars "
                        f"(limit {char_limit}) — NOT written, re-submit shorter"
                    )
                # Numeric score validation: warn on non-numeric but still write
                if fill_type == "numeric_score" and valid_values and ans not in valid_values:
                    invalid_val_count += 1

            # Separate over-limit rows — don't write them; report them for re-submission
            over_limit_rows = {rn: u for rn, u in by_row.items() if u.get("_over_limit")}
            ok_rows         = {rn: u for rn, u in by_row.items() if not u.get("_over_limit")}

            if ok_rows:
                path    = sheet_file[sheet_name]
                patched = _patch_ws(zin.read(path).decode("utf-8"), ok_rows,
                                     sheet_a_num, sheet_a_letter, eff_s_num, eff_s_letter)
                modified[path] = patched.encode("utf-8")
                for u in ok_rows.values():
                    filled += 1
                    sheet_counts[sheet_name] = sheet_counts.get(sheet_name, 0) + 1
                    if u["confidence"] == "high":   high_count += 1
                    elif u["confidence"] == "medium": medium_count += 1
                    else:                             low_count += 1

        # Rewrite the ZIP: swap patched sheets, copy everything else verbatim
        with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename in modified:
                    zout.writestr(info, modified[info.filename])
                else:
                    zout.writestr(info, zin.read(info.filename))

    out.write_bytes(buf.getvalue())

    per_sheet = "  |  ".join(f"{s}: {n}" for s, n in sheet_counts.items()) or "none"
    result = (
        f"RFI Auto-Answer complete: {out.name}\n"
        f"Location: {out}\n"
        f"\n"
        f"Responses written   : {filled}  ({per_sheet})\n"
        f"  Supported (high)  : {high_count}\n"
        f"  Partial (medium)  : {medium_count}\n"
        f"  Review Req. (low) : {low_count}  (KB did not cover — human must fill)\n"
        f"  Category headers  : {merged_skipped}  (merged rows — correctly skipped)\n"
        f"  Skipped sheets    : {skipped}  (skip/pricing/contact/reference — fill manually)\n"
    )
    if truncated_count > 0:
        result += (
            f"\n✂  OVER-LIMIT ANSWERS SKIPPED ({truncated_count}) — these were NOT written to the file.\n"
            f"   Re-submit fill_rfi_xlsx with shorter, complete answers for these rows.\n"
            f"   Condense to fit the limit while keeping all key points and intent:\n"
        )
        for line in over_limit_report:
            result += line + "\n"
    if invalid_val_count > 0:
        result += f"  ⚠ Invalid values  : {invalid_val_count}  (numeric/dropdown sheet — values may need correction)\n"
    if status_col_num is not None:
        result += f"  Status column     : {status_col.upper()}  (colour-coded badges written to qa_freetext sheets only)\n"
    result += f"\nOriginal preserved  : {original}  (unchanged)\n"
    result += f"Cumulative fills    : rfi_filled.xlsx accumulates across multiple calls\n"

    if low_count > 0:
        result += (
            f"\n⚠️  {low_count} question(s) marked 'Review Required'.\n"
            f"   Open rfi_filled.xlsx, filter for [{confirm_tag}], and fill manually\n"
            f"   before sending to {meta['client_name']}."
        )
    else:
        result += f"\n✅ All {filled} answers filled. Review before sending to {meta['client_name']}."

    # ── Write answers.md audit trail ──────────────────────────────────────────
    if audit_rows:
        type_label = _SHEET_TYPE_LABELS.get(sheet_type, "General RFI")
        md_lines = [
            f"# RFI Answers — {meta['client_name']}",
            f"_Generated {datetime.now().strftime('%B %d, %Y %H:%M')} · Sheet type: {type_label}_",
            "",
            "| Row | Sheet | Confidence | Answer | KB Source |",
            "|-----|-------|-----------|--------|-----------|",
        ]
        for a in sorted(audit_rows, key=lambda x: (x["sheet"], x["row"])):
            conf_icon = {"high": "✅", "medium": "⚠️", "low": "🔴"}.get(a["confidence"], "")
            ans_short = a["answer"][:80].replace("|", "\\|") + ("…" if len(a["answer"]) > 80 else "")
            kb = a["kb_source"].replace("|", "\\|") or "—"
            md_lines.append(f"| {a['row']} | {a['sheet']} | {conf_icon} {a['confidence']} | {ans_short} | {kb} |")
        if low_count > 0:
            md_lines += [
                "",
                f"## Review Required ({low_count})",
                "",
            ]
            for a in audit_rows:
                if a["confidence"] == "low":
                    md_lines.append(f"- **Row {a['row']}** ({a['sheet']}): {a['answer'][:120]}")
        audit_out = auto_answer_dir / "answers.md"
        audit_out.write_text("\n".join(md_lines))
        result += f"\nAudit trail         : {audit_out}"

    return result


# ── Proposal generation ────────────────────────────────────────────────────────

@mcp.tool()
def generate_proposal_docx(deal_id: str, intake_json: str) -> str:
    """
    Generate a branded iMocha proposal DOCX using the TA or TM Word template.
    All AI-authored sections are yellow-highlighted for analyst review.

    GROUNDING REQUIREMENT — before authoring intake_json:
      1. Call get_deal_context to load the RFP text and all prior stage outputs.
      2. Author every section from the RFP content and the iMocha KB loaded in this
         project context — not from general Claude knowledge about iMocha.
      3. For any field where the RFP or KB does not provide a clear answer, write
         [CONFIRM: <what to fill in>] rather than inventing client-specific content.
         The yellow highlights in the DOCX are the reviewer's signal to verify these.
    Strips Word Online lock parts (intelligence2.xml, SharePoint parts) so the file is editable.
    Saves to RFP/ subfolder.

    Args:
        deal_id:     Client name (e.g. "Accenture")
        intake_json: JSON with all proposal content authored by Claude. Schema:
          {
            "product": "TA" or "TM" (optional — auto-detected from RFP if omitted),
            "rfp_name": "proposal title",
            "customer_display_name": "client name as shown in document",
            "prepared_for": "client procurement contact name/title",
            "spoc_name": "iMocha SPOC full name",
            "spoc_email": "iMocha SPOC email",
            "exec_summary": {
              "pleased":   "cover letter warm intro (2-3 sentences, no newlines)",
              "aligned":   "strategic alignment (use \\n between paragraphs)",
              "confident": "bullets starting with '• ', separated by \\n"
            },
            "scope_intro": "scope paragraph (use '• ' prefix for bullets)",
            "deliverables": ["8-12 bullet strings"],
            "integrations": "comma-separated platforms (TA only, empty for TM)",
            "integrations_content": "2-3 sentence integration para (TA only)",
            "hcm_hris": "TM only or null",
            "lms_lxp": "TM only or null",
            "talent_marketplace": "TM only or null",
            "content_provider": "TM only or null"
          }
          Use [CONFIRM: description] for any field missing client-specific info.
    """
    try:
        intake = json.loads(intake_json)
    except json.JSONDecodeError as e:
        return f"Error: invalid intake_json — {e}"

    from docx_engine import generate_docx

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])

    # Resolve product: intake field → meta auto-detection → fallback "TA"
    product = intake.get("product") or meta.get("product_type") or "TA"
    if product == "Both":
        # "Both" can't select a single template — default to TA and note it
        product = "TA"
    # Normalise: accept "SI" / "TM" / "Talent Management" → "TM"
    if product.upper() in ("TM", "SI", "TALENT MANAGEMENT", "SKILLS INTELLIGENCE"):
        product = "TM"
    else:
        product = "TA"
    intake["product"] = product  # ensure intake is consistent for the template engine

    tpl_name = "TM_Proposal_template.docx" if product == "TM" else "TA_Proposal_template.docx"
    tpl_path = TEMPLATES_DIR / tpl_name
    if not tpl_path.exists():
        return f"Error: template not found at {tpl_path}. Copy {tpl_name} into bidbuddy-mcp/templates/"

    try:
        docx_bytes = generate_docx(tpl_path, intake)
    except Exception as e:
        import traceback
        return f"Error generating DOCX: {e}\n{traceback.format_exc()}"
    rfp_folder = base / "RFP"
    rfp_folder.mkdir(parents=True, exist_ok=True)

    safe = re.sub(r"[^a-z0-9]+", "_", intake.get("customer_display_name", deal_id).lower()).strip("_")
    filename = f"iMocha_{safe}_{product}_Proposal_DRAFT.docx"
    out = rfp_folder / filename
    out.write_bytes(docx_bytes)

    confirm_count = sum(
        1 for v in [
            intake.get("exec_summary", {}).get("pleased", ""),
            intake.get("exec_summary", {}).get("aligned", ""),
            intake.get("exec_summary", {}).get("confident", ""),
            intake.get("scope_intro", ""),
            *intake.get("deliverables", []),
        ]
        if "[CONFIRM:" in str(v)
    )

    # Mark proposal stage complete
    completed = meta.setdefault("stages_completed", [])
    if "proposal" not in completed:
        completed.append("proposal")
    meta["stage"] = "proposal_review"
    _save_meta(deal_id, meta)

    return (
        f"Proposal generated: {filename}\n"
        f"Saved to: {out}\n"
        f"Size: {len(docx_bytes):,} bytes\n\n"
        f"Yellow highlights = all AI-authored sections (review before sending).\n"
        f"[CONFIRM:] markers found: {confirm_count} — resolve all before client submission.\n\n"
        f"Open in Word to review. Upload to OneDrive to verify it opens in edit mode (not read-only)."
    )


# ── Deal insights ──────────────────────────────────────────────────────────────

@mcp.tool()
def save_deal_insights(deal_id: str, insights_md: str) -> str:
    """
    Persist the strengths / weaknesses / win-strategy analysis you just generated
    for a deal after qualification scoring. Saves to Deal Qualification/deal_insights.md
    so get_deal_context loads it automatically in future sessions.

    Call this immediately after you have delivered the insights analysis to the user
    in chat — pass exactly the markdown you showed them.

    Format expected (use this structure so future context loads cleanly):

    ## Strengths
    - Strength 1
    - Strength 2

    ## Weaknesses / Risks
    - Risk 1
    - Risk 2

    ## Win Strategy
    One or two sentence recommendation.

    ## Recommended Next Steps
    1. Step one
    2. Step two

    Args:
        deal_id:     Client name (e.g. "Accenture")
        insights_md: Full markdown text of the insights analysis (as shown to user)
    """
    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    dq_dir = base / "Deal Qualification"
    dq_dir.mkdir(parents=True, exist_ok=True)

    out = dq_dir / "deal_insights.md"
    header = f"# Deal Insights — {meta['client_name']} ({meta['product']})\n_Generated {datetime.now().strftime('%B %d, %Y')}_\n\n"
    out.write_text(header + insights_md.strip())

    completed = meta.setdefault("stages_completed", [])
    if "deal_insights" not in completed:
        completed.append("deal_insights")
    _save_meta(deal_id, meta)

    return f"Insights saved: {out}\n({len(insights_md):,} chars — will load automatically via get_deal_context)"


# ── RFP explicit asks ───────────────────────────────────────────────────────────

@mcp.tool()
def save_explicit_asks(deal_id: str, asks_text: str) -> str:
    """
    Save customer explicit asks / late-breaking requirements for a deal at the RFP stage.
    Persists to RFP/explicit_asks.md so get_deal_context loads it automatically in
    future sessions — ensuring proposal generation always has this context.

    Use this whenever the user provides new inputs in chat: pasted email threads,
    verbal briefings, call notes, or additional requirements not in the original RFP.
    Call it before (or just after) generate_proposal_docx so the content is never lost.

    Write the asks in the format that will be most useful to proposal generation:
    - Direct requirements: what the client explicitly asked for
    - Source: where it came from (email from X on date, verbal from Y on call)
    - Priority: MUST HAVE / NICE TO HAVE if the user indicated

    Example:
    ## From email — procurement@accenture.com (Aug 14)
    - MUST HAVE: The proposal must include a dedicated section on data residency in EU
    - MUST HAVE: Pricing breakdown by module (not bundled)

    ## From discovery call (Aug 16) — noted by Aryan
    - NICE TO HAVE: Reference to similar BFSI clients in India

    Args:
        deal_id:   Client name (e.g. "Accenture")
        asks_text: Full text of the explicit asks (markdown, plain prose, or bullet list)
    """
    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    rfp_dir = base / "RFP"
    rfp_dir.mkdir(parents=True, exist_ok=True)

    out = rfp_dir / "explicit_asks.md"
    # Append if file already exists (multiple sessions may add asks)
    existing = out.read_text() if out.exists() else ""
    separator = f"\n\n---\n_Added {datetime.now().strftime('%B %d, %Y %H:%M')}_\n\n" if existing else ""
    out.write_text(existing + separator + asks_text.strip())

    completed = meta.setdefault("stages_completed", [])
    if "explicit_asks" not in completed:
        completed.append("explicit_asks")
    _save_meta(deal_id, meta)

    char_total = len(out.read_text())
    return (
        f"Explicit asks saved: {out}\n"
        f"Added {len(asks_text):,} chars  |  File total: {char_total:,} chars\n"
        f"Will load automatically via get_deal_context in future sessions."
    )


# ── RFI verification helpers ───────────────────────────────────────────────────

@mcp.tool()
def inspect_rfi_xlsx(deal_id: str, columns: str = "", max_rows: int = 10) -> str:
    """
    Read actual cell values from rfi_filled.xlsx so Claude can verify its own work
    with certainty instead of guessing.

    Call this immediately after fill_rfi_xlsx to confirm:
      - Which column the answers landed in
      - Whether the text looks correct and complete
      - Whether the char limit was respected

    Args:
        deal_id:  Client name (e.g. "AB InBev")
        columns:  Comma-separated column letters to inspect (e.g. "B,N").
                  Leave empty to auto-show every sheet's answer column from col_map.
        max_rows: Max answer rows to show per sheet (default 10). Use 0 for all rows.
    """
    import openpyxl as _opx
    from openpyxl.cell.cell import MergedCell as _MC

    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    auto_dir = base / "RFI" / "Auto Answer"

    filled = auto_dir / "rfi_filled.xlsx"
    if not filled.exists():
        return "rfi_filled.xlsx not found. Run fill_rfi_xlsx first."

    col_map_path = auto_dir / "rfi_col_map.json"
    col_map: dict = json.loads(col_map_path.read_text()) if col_map_path.exists() else {}

    # Which column letters to inspect
    if columns.strip():
        target_letters = [c.strip().upper() for c in columns.split(",") if c.strip()]
    else:
        # default: answer column per sheet from col_map
        target_letters = list({v.get("answer_col_letter", "B").upper()
                                for v in col_map.values() if v.get("answer_col_letter")})
        if not target_letters:
            target_letters = ["B"]

    def _col_num(letter: str) -> int:
        letter = letter.upper().strip()
        return sum((ord(ch) - 64) * (26 ** i) for i, ch in enumerate(reversed(letter)))

    wb = _opx.load_workbook(filled, data_only=True)
    lines = [
        f"═══════════════════════════════════════════════════",
        f"VERIFY: rfi_filled.xlsx  —  {filled}",
        f"Inspecting columns: {', '.join(target_letters)}",
        f"═══════════════════════════════════════════════════",
        "",
    ]

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_meta = col_map.get(sheet_name, {})
        fill_type = sheet_meta.get("fill_type", "?")
        char_limit = sheet_meta.get("char_limit")

        # Determine which col numbers to inspect for this sheet
        inspect_nums = [_col_num(l) for l in target_letters]

        # Collect non-empty answer cells
        found_rows = []
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell, _MC):
                    continue
                if cell.column not in inspect_nums:
                    continue
                val = cell.value
                if val is None or str(val).strip() == "":
                    continue
                col_letter = cell.column_letter
                text = str(val)
                over = f"  ⚠ OVER LIMIT ({len(text)}/{char_limit})" if char_limit and len(text) > char_limit else ""
                found_rows.append((cell.row, col_letter, text, over))

        if not found_rows:
            lines.append(f"Sheet '{sheet_name}'  [{fill_type}]  — no content in {target_letters}")
            lines.append("")
            continue

        limit_label = f"  char_limit={char_limit}" if char_limit else ""
        lines.append(f"Sheet '{sheet_name}'  [{fill_type}]{limit_label}  —  {len(found_rows)} cells with content:")
        display = found_rows if max_rows == 0 else found_rows[:max_rows]
        for rn, cl, text, over in display:
            preview = text[:120] + ("…" if len(text) > 120 else "")
            lines.append(f"  Row {rn:>3}  col {cl}  ({len(text):>4} chars){over}")
            lines.append(f"           {preview}")
        if max_rows and len(found_rows) > max_rows:
            lines.append(f"  … {len(found_rows) - max_rows} more rows (pass max_rows=0 to see all)")
        lines.append("")

    lines.append(f"File size: {filled.stat().st_size:,} bytes")
    return "\n".join(lines)


@mcp.tool()
def reset_rfi_filled(deal_id: str) -> str:
    """
    Delete rfi_filled.xlsx so the next fill_rfi_xlsx call starts from a clean copy
    of the original instead of accumulating on top of previous (possibly wrong) fills.

    Use this when:
      - Answers landed in the wrong column and need to be rewritten from scratch
      - The file has accumulated duplicate answers across multiple fill calls
      - You want to retry the entire fill with corrected parameters

    The original rfi_original.xlsx is NEVER touched.

    Args:
        deal_id: Client name (e.g. "AB InBev")
    """
    meta = _load_meta(deal_id)
    base = Path(meta["base_path"])
    auto_dir = base / "RFI" / "Auto Answer"

    filled = auto_dir / "rfi_filled.xlsx"
    if not filled.exists():
        return "rfi_filled.xlsx does not exist — nothing to reset."

    size = filled.stat().st_size
    filled.unlink()
    return (
        f"✓ rfi_filled.xlsx deleted ({size:,} bytes).\n"
        f"Next fill_rfi_xlsx call will create a fresh copy from rfi_original.xlsx.\n"
        f"Original preserved: {auto_dir / 'rfi_original.xlsx'}"
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
