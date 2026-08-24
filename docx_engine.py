"""
DOCX template engine — Python port of BidTrack generate-proposal.ts
Manipulates branded Word templates at ZIP/XML level to preserve all formatting.
"""

import io
import re
import zipfile
from pathlib import Path

YELLOW_HIGHLIGHT = '<w:highlight w:val="yellow"/>'

# ── XML helpers ────────────────────────────────────────────────────────────────

def xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def add_highlight_to_rpr(rpr: str) -> str:
    if not rpr:
        return f"<w:rPr>{YELLOW_HIGHLIGHT}</w:rPr>"
    if "<w:highlight" in rpr:
        return re.sub(r"<w:highlight[^/]*//>", YELLOW_HIGHLIGHT, rpr)
    return rpr.replace("</w:rPr>", f"{YELLOW_HIGHLIGHT}</w:rPr>")

def sanitize(text: str) -> str:
    return re.sub(r"[\r\n]+", " ", str(text or "")).strip()

def sanitize_multiline(text: str) -> str:
    return str(text or "").replace("\r", "").strip()

# ── Template token configs ─────────────────────────────────────────────────────

TM_EXEC_PARA1 = (
    "Through this document, we highlight the critical shifts shaping workforce transformation "
    "and demonstrate why iMocha is the ideal partner to accelerate [Customer Name]’s journey "
    "toward skills intelligence. By combining AI-powered Skills Inference and Validation, enriched "
    "skills data, and advanced analytics for mobility, upskilling, and workforce planning, iMocha "
    "creates a continuous cycle of visibility and growth powered by real-time, validated skills insights."
)

TM_EXEC_PARA2 = (
    "We are confident that iMocha’s enterprise-grade Skills Intelligence will help [Customer Name] "
    "unlock measurable impact—bridging the gap between talent supply and business demand—while "
    "transforming how skills drive performance, mobility, and organizational readiness. We look forward "
    "to partnering on this strategic initiative."
)

def _build_ta_subs(intake: dict) -> list[tuple[str, str, str]]:
    """Returns list of (token, value, strategy) for TA template."""
    cdn = sanitize(intake.get("customer_display_name", ""))
    return [
        # strategy: paragraph
        ("Customer (CUSTOMER)", sanitize(intake.get("customer_display_name", "")), "paragraph"),
        ("CUSTOMER Team", sanitize(intake.get("prepared_for", "")), "paragraph"),
        ("To:CUSTOMER Team", f"To: {sanitize(intake.get('prepared_for') or intake.get('customer_display_name', ''))}", "paragraph"),
        ("Sales person", sanitize(intake.get("spoc_name", "")), "paragraph"),
        ("iMocha@imocha.io ", sanitize(intake.get("spoc_email", "")), "paragraph"),
        ("Subject: Proposal Submission –<Mention subject for cover page>",
         f"Subject: Proposal Submission — {sanitize(intake.get('rfp_name', ''))}", "paragraph"),
        ("Dear <Customer name>,", f"Dear {cdn},", "paragraph"),
        ("<Cover page details>", sanitize(intake.get("exec_summary", {}).get("pleased", "")), "paragraph"),
        ("<Write strategic objective of customer>",
         sanitize_multiline(intake.get("exec_summary", {}).get("aligned", "")), "paragraph"),
        ("<Mention the details for what customer is looking for>",
         sanitize_multiline(intake.get("exec_summary", {}).get("confident", "")), "paragraph"),
        ("<Instuction: Write the details scope of work and requirement from customer; do not assume anything>",
         sanitize_multiline(intake.get("scope_intro", "")), "paragraph"),
        ("<Instruction: Pick only those modules from below which are applicable to the customer requirements>",
         "", "paragraph"),
        # strategy: direct (XML-encoded tokens inside <w:t>)
        ("&lt;RFP Name&gt;", xml_escape(sanitize(intake.get("rfp_name", ""))), "direct"),
        ("CUSTOMER", xml_escape(cdn), "direct"),
    ]

def _build_tm_subs(intake: dict) -> list[tuple[str, str, str]]:
    cdn = sanitize(intake.get("customer_display_name", ""))

    hr_parts = []
    if intake.get("hcm_hris"): hr_parts.append(f"HCM/HRIS: {sanitize(intake['hcm_hris'])}")
    if intake.get("lms_lxp"): hr_parts.append(f"LMS/LXP: {sanitize(intake['lms_lxp'])}")
    if intake.get("talent_marketplace"): hr_parts.append(f"Talent Marketplace: {sanitize(intake['talent_marketplace'])}")
    if intake.get("content_provider"): hr_parts.append(f"Content Provider: {sanitize(intake['content_provider'])}")
    hr_text = " · ".join(hr_parts) if hr_parts else "[CONFIRM: HR tech ecosystem — specify HCM/HRIS, LMS/LXP, talent marketplace, content provider]"

    return [
        # paragraph
        ("(Change this to reflect the customer's RFP title)", sanitize(intake.get("rfp_name", "")), "paragraph"),
        (f"Business Proposal: Skills Intelligence for [Customer Name]",
         f"Business Proposal: Skills Intelligence for {cdn}", "paragraph"),
        ("Prepared For:Name", f"Prepared For: {sanitize(intake.get('prepared_for', ''))}", "paragraph"),
        ("Customer Name", cdn, "paragraph"),
        ("[Customer/Partner Email]", "[CONFIRM: client procurement contact email address]", "paragraph"),
        ("<iMocha Sales Representative>", sanitize(intake.get("spoc_name", "")), "paragraph"),
        ("iMochaname@imocha.io | +91 xxxxx xxxxx", sanitize(intake.get("spoc_email", "")), "paragraph"),
        ("<Sales Representative>Designation, iMochaname@imocha.io | +91 xxxxx xxxxx",
         f"{sanitize(intake.get('spoc_name', ''))}, iMocha | {sanitize(intake.get('spoc_email', ''))}", "paragraph"),
        (TM_EXEC_PARA1, sanitize(intake.get("exec_summary", {}).get("aligned", "")), "paragraph"),
        (TM_EXEC_PARA2, sanitize(intake.get("exec_summary", {}).get("confident", "")), "paragraph"),
        ("(Change this to reflect the customer's HR Tech Ecosystem for eg. SAP SF, Workday etc)", hr_text, "paragraph"),
        # direct
        ("[Customer Name]", xml_escape(cdn), "direct"),
        ("[Company Name]", xml_escape(cdn), "direct"),
        ("[Company Names]", xml_escape(cdn), "direct"),
        ("[HCM / HRIS]", xml_escape(sanitize(intake.get("hcm_hris") or "[CONFIRM: HCM/HRIS system]")), "direct"),
        ("[LMS/LXP]", xml_escape(sanitize(intake.get("lms_lxp") or "[CONFIRM: LMS/LXP platform]")), "direct"),
        ("[LMS /LXP]", xml_escape(sanitize(intake.get("lms_lxp") or "[CONFIRM: LMS/LXP platform]")), "direct"),
        ("[Talent Marketplace]", xml_escape(sanitize(intake.get("talent_marketplace") or "[CONFIRM: talent marketplace]")), "direct"),
        ("[Content Provider]", xml_escape(sanitize(intake.get("content_provider") or "[CONFIRM: content provider]")), "direct"),
        ("[Project Management System]", xml_escape("[CONFIRM: project management system]"), "direct"),
    ]

TA_ANCHORS = {
    "deliverables_heading": "Key Deliverables: ",
    "deliverables_subheading": "In Scope Deliverables",
    "scope_intro_before_subheading": False,
}

TM_ANCHORS = {
    "deliverables_heading": "7. Proposal Summary",
    "deliverables_subheading": "In Scope Deliverables",
    "scope_intro_before_subheading": True,
}

# ── Paragraph-level substitution ───────────────────────────────────────────────

def _discover_bullet_num_id(xml: str) -> str:
    m = re.search(r'ListParagraph[\s\S]{1,400}?<w:numId w:val="(\d+)"', xml)
    if m:
        return m.group(1)
    fb = re.search(r'<w:numId w:val="(\d+)"', xml)
    return fb.group(1) if fb else "1"

def _decode_para_text(para: str) -> str:
    matches = re.findall(r"<w:t(?:[^>]*)>([^<]*)</w:t>", para)
    result = ""
    for m in matches:
        result += m.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return result

def apply_paragraph_substitutions(xml: str, subs: list[tuple[str, str]]) -> str:
    # Self-closing <w:p attr/> paragraphs have no </w:p>, causing the non-greedy
    # regex to span into the next paragraph's closing tag. Expand them first.
    xml = re.sub(r'<w:p ([^>]*)\/>', r'<w:p \1></w:p>', xml)
    bullet_num_id = _discover_bullet_num_id(xml)

    def replace_para(m):
        para = m.group(0)
        full_text = _decode_para_text(para)

        for token, value in subs:
            if full_text.strip() != token.strip():
                continue

            p_attrs_m = re.match(r"^<w:p([^>]*)>", para)
            p_attrs = p_attrs_m.group(1) if p_attrs_m else ""
            ppr_m = re.search(r"<w:pPr>[\s\S]*?</w:pPr>", para)
            ppr = ppr_m.group(0) if ppr_m else ""
            rpr_m = re.search(r"<w:rPr>[\s\S]*?</w:rPr>", para)
            rpr = rpr_m.group(0) if rpr_m else ""

            clean_ppr = re.sub(r"<w:numPr>[\s\S]*?</w:numPr>", "", ppr)
            is_list = bool(re.search(r'pStyle w:val="ListParagraph"', ppr))
            normal_ppr = "<w:pPr/>" if is_list else clean_ppr
            highlighted_rpr = add_highlight_to_rpr(rpr)

            if "\n" not in value:
                return (
                    f'<w:p{p_attrs}>{normal_ppr}<w:r>{highlighted_rpr}'
                    f'<w:t xml:space="preserve">{xml_escape(value)}</w:t></w:r></w:p>'
                )

            lines = [l.strip() for l in value.split("\n") if l.strip()]
            paras = []
            for line in lines:
                if line.startswith("• "):
                    bullet_text = line[2:]
                    bullet_ppr = (
                        f'<w:pPr><w:pStyle w:val="ListParagraph"/>'
                        f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{bullet_num_id}"/></w:numPr></w:pPr>'
                    )
                    paras.append(
                        f'<w:p{p_attrs}>{bullet_ppr}<w:r>{highlighted_rpr}'
                        f'<w:t xml:space="preserve">{xml_escape(bullet_text)}</w:t></w:r></w:p>'
                    )
                else:
                    paras.append(
                        f'<w:p{p_attrs}>{normal_ppr}<w:r>{highlighted_rpr}'
                        f'<w:t xml:space="preserve">{xml_escape(line)}</w:t></w:r></w:p>'
                    )
            return "\n".join(paras)

        return para

    return re.sub(r"<w:p[ >][\s\S]*?</w:p>", replace_para, xml)

# ── Direct substitution with highlight ────────────────────────────────────────

def _escape_for_regex(s: str) -> str:
    return re.escape(s)

def apply_direct_sub_with_highlight(xml: str, token: str, value: str) -> str:
    if token not in xml:
        return xml

    # Pass 1: strict — clean <w:r>...<w:t>content</w:t></w:r>
    def strict_replace(m):
        run_open, rpr, t_open, t_content, t_close = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if token not in t_content:
            return m.group(0)
        new_content = t_content.replace(token, value)
        new_rpr = add_highlight_to_rpr(rpr)
        return f"{run_open}{new_rpr}{t_open}{new_content}{t_close}"

    result = re.sub(
        r"(<w:r(?:\s[^>]*)?>)((?:<w:rPr>[\s\S]*?</w:rPr>)?)(<w:t(?:[^>]*)>)([^<]*)(<\/w:t><\/w:r>)",
        strict_replace,
        xml,
    )

    if token not in result:
        return result

    # Pass 2: loose — up to 500 chars between </w:t> and </w:r>
    def loose_replace(m):
        run_open, rpr, t_open, t_content, t_close = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        new_content = t_content.replace(token, value)
        new_rpr = add_highlight_to_rpr(rpr)
        return f"{run_open}{new_rpr}{t_open}{new_content}{t_close}"

    token_re = _escape_for_regex(token)
    result = re.sub(
        rf"(<w:r(?:\s[^>]*)?>)((?:<w:rPr>[\s\S]*?</w:rPr>)?)(<w:t(?:[^>]*)>)([^<]*{token_re}[^<]*)(</w:t>[\s\S]{{0,500}}?</w:r>)",
        loose_replace,
        result,
    )

    # Last resort: plain replace without highlight
    if token in result:
        result = result.replace(token, value)

    return result

# ── TOC dirty flag ─────────────────────────────────────────────────────────────

def mark_toc_field_dirty(xml: str) -> str:
    def replacer(m):
        open_tag, close_tag = m.group(1), m.group(2)
        offset = m.start()
        nearby = xml[offset: offset + 4000]
        if re.search(r"instrText[^>]*>\s*TOC\b", nearby):
            return f'{open_tag} w:dirty="true"{close_tag}'
        return m.group(0)

    return re.sub(r'(<w:fldChar\s+w:fldCharType="begin")(\s*/>)', replacer, xml)

# ── Deliverables injection ─────────────────────────────────────────────────────

def _find_heading_para_end(xml: str, heading_text: str) -> int:
    for m in re.finditer(r"<w:p[ >][\s\S]*?</w:p>", xml):
        if _decode_para_text(m.group(0)).strip() == heading_text.strip():
            return m.end()
    return -1

def _build_bullet_paragraphs(deliverables: list[str], num_id: str) -> str:
    highlighted_rpr = f"<w:rPr>{YELLOW_HIGHLIGHT}</w:rPr>"
    paras = []
    for text in deliverables:
        paras.append(
            f'<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
            f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr></w:pPr>'
            f'<w:r>{highlighted_rpr}<w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r></w:p>'
        )
    return "\n".join(paras)

def inject_deliverables(
    xml: str,
    deliverables: list[str],
    anchors: dict,
    scope_intro: str | None = None,
) -> str:
    num_id = _discover_bullet_num_id(xml)
    bullets = _build_bullet_paragraphs(deliverables, num_id)
    rpr_body = f'<w:rPr><w:rFonts w:ascii="Poppins" w:hAnsi="Poppins" w:cs="Poppins"/><w:sz w:val="22"/><w:szCs w:val="22"/>{YELLOW_HIGHLIGHT}</w:rPr>'

    insert_at = _find_heading_para_end(xml, anchors["deliverables_heading"])
    if insert_at == -1:
        print(f"[docx_engine] WARNING: anchor heading not found: '{anchors['deliverables_heading']}' — appending at body end")
        return xml.replace("</w:body>", bullets + "</w:body>")

    injected = ""

    if scope_intro and anchors.get("scope_intro_before_subheading"):
        injected += (
            f'<w:p><w:pPr><w:pStyle w:val="NormalWeb"/></w:pPr>'
            f'<w:r>{rpr_body}<w:t xml:space="preserve">{xml_escape(sanitize(scope_intro))}</w:t></w:r></w:p>\n'
        )

    if anchors.get("deliverables_subheading"):
        injected += (
            f'<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
            f'<w:r><w:rPr>{YELLOW_HIGHLIGHT}</w:rPr>'
            f'<w:t xml:space="preserve">{xml_escape(anchors["deliverables_subheading"])}</w:t></w:r></w:p>\n'
        )

    injected += bullets

    return xml[:insert_at] + "\n" + injected + xml[insert_at:]

# ── ZIP part stripping ─────────────────────────────────────────────────────────

def _is_excluded_part(filename: str) -> bool:
    """Return True for any SharePoint/Copilot part that blocks Word Online editing."""
    if filename in ("docProps/custom.xml", "word/intelligence2.xml"):
        return True
    if re.match(r"^customXml/(item|itemProps)\d+\.xml$", filename):
        return True
    if re.match(r"^customXml/_rels/item\d+\.xml\.rels$", filename):
        return True
    return False

def _strip_rels(xml: str) -> str:
    xml = re.sub(r'<Relationship[^>]*custom-properties[^>]*/>', "", xml)
    return xml

def _strip_doc_rels(xml: str) -> str:
    # Strip ALL customXml item refs (\d+ not [123]) and intelligence2 relationship
    xml = re.sub(r'<Relationship[^>]*Target="\.\./customXml/item\d+\.xml"[^>]*/>', "", xml)
    xml = re.sub(r'<Relationship[^>]*intelligence2[^>]*/>', "", xml)
    return xml

def _strip_content_types(xml: str) -> str:
    xml = re.sub(r'<Override[^>]*PartName="/docProps/custom\.xml"[^>]*/>', "", xml)
    # Strip ALL customXml item + itemProps entries (\d+ not [123])
    xml = re.sub(r'<Override[^>]*PartName="/customXml/item(?:Props)?\d+\.xml"[^>]*/>', "", xml)
    xml = re.sub(r'<Override[^>]*intelligence2[^>]*/>', "", xml)
    return xml

def _strip_protection(xml: str) -> str:
    xml = re.sub(r"<w:documentProtection\b[^>]*/?>", "", xml)
    xml = re.sub(r"<w:documentProtection\b[\s\S]*?</w:documentProtection>", "", xml)
    xml = re.sub(r"<w:writeProtection\b[^>]*/?>", "", xml)
    xml = re.sub(r"<w:writeProtection\b[\s\S]*?</w:writeProtection>", "", xml)
    if "w:updateFields" not in xml:
        xml = xml.replace("</w:settings>", '<w:updateFields w:val="1"/></w:settings>')
    return xml

# ── Main entry point ───────────────────────────────────────────────────────────

def generate_docx(template_path: Path, intake: dict) -> bytes:
    product = intake.get("product", "TA")
    print(f"[docx_engine v4] generate_docx called — product={product}, template={template_path.name}")
    subs = _build_tm_subs(intake) if product == "TM" else _build_ta_subs(intake)
    anchors = TM_ANCHORS if product == "TM" else TA_ANCHORS

    para_subs = [(t, v) for t, v, s in subs if s == "paragraph"]
    direct_subs = [(t, v) for t, v, s in subs if s == "direct"]

    template_bytes = template_path.read_bytes()
    in_buf = io.BytesIO(template_bytes)
    out_buf = io.BytesIO()

    with zipfile.ZipFile(in_buf, "r") as zin:
        all_parts = [i.filename for i in zin.infolist()]
        stripped = [p for p in all_parts if _is_excluded_part(p)]
        print(f"[docx_engine v4] stripping {len(stripped)} SP/Copilot parts: {stripped or 'none'}")
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if _is_excluded_part(item.filename):
                    continue

                data = zin.read(item.filename)

                if item.filename == "word/document.xml":
                    xml = data.decode("utf-8")
                    # Paragraph substitutions first (handles split-run tokens)
                    xml = apply_paragraph_substitutions(xml, para_subs)
                    # Direct substitutions (inline tokens in <w:t>)
                    for token, value in direct_subs:
                        xml = apply_direct_sub_with_highlight(xml, token, value)
                    # TOC dirty flag
                    xml = mark_toc_field_dirty(xml)
                    # Inject deliverables
                    scope_intro_for_tm = intake.get("scope_intro") if product == "TM" else None
                    xml = inject_deliverables(xml, intake.get("deliverables", []), anchors, scope_intro_for_tm)
                    data = xml.encode("utf-8")

                elif item.filename == "_rels/.rels":
                    data = _strip_rels(data.decode("utf-8")).encode("utf-8")

                elif item.filename == "word/_rels/document.xml.rels":
                    data = _strip_doc_rels(data.decode("utf-8")).encode("utf-8")

                elif item.filename == "[Content_Types].xml":
                    data = _strip_content_types(data.decode("utf-8")).encode("utf-8")

                elif item.filename == "word/settings.xml":
                    data = _strip_protection(data.decode("utf-8")).encode("utf-8")

                zout.writestr(item, data)

    return out_buf.getvalue()
