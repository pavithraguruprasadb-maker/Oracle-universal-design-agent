"""
Oracle University — Training Design Agent  (Enhanced v2)
Full-Stack: Multi-Step Streamlit Frontend + AI Backend (Groq / LLaMA-3.3-70B)

Enhancements over v1:
  1.  Pre-processing semantic classification (instructional / conceptual / procedural)
  2.  Source-to-section traceability map rendered as a structured table
  3.  Prerequisite-chain sequencing rule enforced in prompt
  4.  Design Master Class principles loaded from file / constant (no paraphrase)
  5.  Post-generation format-validation (second AI call)
  6.  Sample Completed Design Document injected as few-shot context
  7.  Tone / detail calibration against sample (same fix as 6)
  8.  build_word() parses markdown tables → proper python-docx Table objects
      with named styles (Heading 1-3, Body Text)
  9.  Job-role field: multiselect list  +  free-text "other role" input
 10.  URL scraper recursively follows sub-section links on the same domain

Install:
    pip install streamlit requests groq pdfplumber python-pptx python-docx \
                Pillow pytesseract pdf2image reportlab beautifulsoup4 urllib3

Run:
    streamlit run master_tdd_enhanced.py
"""

# ─── IMPORTS ────────────────────────────────────────────────────────────────
import streamlit as st
import time, io, re, os, json
import requests
from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from collections import defaultdict

# --- File Extraction ---
import pdfplumber
from pptx import Presentation
from docx import Document as DocxRead
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

# --- AI ---
from groq import Groq

# --- Document Generation ---
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Training Design Agent | Oracle University",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── MANDATORY SECTIONS ───────────────────────────────────────────────────────
MANDATORY_SECTIONS = [
    "COURSE OVERVIEW",
    "PERSONA INFORMATION",
    "IMPLEMENTATION READINESS",
    "GTM MESSAGING",
    "COURSE COVERAGE TABLE",
    "CASE STUDY",
    "QA CHECKLIST",
]


# ─── DESIGN MASTER CLASS PRINCIPLES (Enhancement 4) ──────────────────────────
# Load from file if present, otherwise use embedded constant.
_DMC_FILE = os.path.join(os.path.dirname(__file__), "design_master_class.txt")
if os.path.exists(_DMC_FILE):
    with open(_DMC_FILE, "r", encoding="utf-8") as _f:
        DESIGN_MASTER_CLASS_PRINCIPLES = _f.read()
else:
    DESIGN_MASTER_CLASS_PRINCIPLES = """
=== ORACLE DESIGN MASTER CLASS — FULL FRAMEWORK ===

PRINCIPLE 1 — 80/20 CONTENT FOCUS
  Identify the 20 % of product capabilities that deliver 80 % of business value for the
  target role. Anchor every module to at least one of these high-value capabilities.
  Explicitly call out the rationale in the Course Overview.

PRINCIPLE 2 — BLOOM'S TAXONOMY ALIGNMENT
  Map every learning objective to a Bloom's level verb appropriate for the audience tier:
    Beginner    → Remember / Understand  (define, describe, identify, explain)
    Intermediate→ Apply / Analyse        (configure, implement, compare, troubleshoot)
    Advanced    → Evaluate / Create      (design, optimise, justify, architect)
  Objectives must be SMART (Specific, Measurable, Achievable, Relevant, Time-bound).

PRINCIPLE 3 — MICROLEARNING ARCHITECTURE
  Every video or concept block: 3–7 minutes maximum.
  Every module: no more than 4 activities (Concept → Demo → Lab → Scenario).
  Provide an estimated seat-time per module and a cumulative course total.

PRINCIPLE 4 — BALANCED ACTIVITY MIX
  Each module MUST include exactly:
    1 × Concept explanation  (lecture / reading)
    1 × Instructor/recorded Demo
    1 × Hands-on Lab (guided or open-ended, scaled to level)
    1 × Scenario or Case-study question

PRINCIPLE 5 — GTM MESSAGING FRAMEWORK
  Produce a single crisp USP sentence (≤ 25 words).
  List 3–5 business problems the course solves.
  List 5–7 learner takeaways phrased as business outcomes.

PRINCIPLE 6 — PREREQUISITE CHAIN (FOUNDATIONAL → ADVANCED)
  Arrange modules so every module builds on the prior one.
  Module 1 is always foundational (concepts, terminology, architecture overview).
  Advanced configuration / design modules come last.
  State explicit prerequisites between modules inside the Coverage Table.

PRINCIPLE 7 — AUDIENCE PERSONA FIDELITY
  The Persona section must capture: Role title, day-to-day pain points, motivations,
  tech-savviness, and the primary business metric they are measured on.

PRINCIPLE 8 — TRACEABILITY & CITATIONS
  Every factual claim must carry a [FILE: …] or [URL: …] tag.
  If no source is available, tag with [ORACLE KNOWLEDGE BASE].
  The document must end with a TRACEABILITY MAP table.

=== END DESIGN MASTER CLASS FRAMEWORK ===
"""


# ─── SAMPLE COMPLETED DESIGN DOCUMENT (Enhancements 6 & 7) ───────────────────
_SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "sample_design_document.txt")
if os.path.exists(_SAMPLE_FILE):
    with open(_SAMPLE_FILE, "r", encoding="utf-8") as _f:
        SAMPLE_DESIGN_DOCUMENT = _f.read()
else:
    SAMPLE_DESIGN_DOCUMENT = """
=== REFERENCE SAMPLE — MATCH THIS LEVEL OF DETAIL AND TONE ===

--- COURSE OVERVIEW
Course Title : Oracle Integration Cloud Fundamentals
Product      : Oracle Integration Cloud (OIC) 3.0
Duration     : 12 hours (8 × 90-min modules)
Delivery     : Instructor-led + self-paced eLearning
Version      : Jan 2025 | Oracle University

This course equips Developers and Integration Architects with the skills to design,
build, and monitor enterprise integrations using Oracle Integration Cloud. Learners
will exit the course able to configure REST and SOAP adapters, build orchestration
flows, and instrument error handling and monitoring dashboards.

80/20 Rationale: The two capabilities — REST adapter configuration and Orchestration
flow design — account for ~80 % of production OIC usage. Modules 3–6 therefore
receive the deepest treatment. [ORACLE KNOWLEDGE BASE]

--- PERSONA INFORMATION
Primary Persona : Integration Developer
  Pain Points   : Manual data movement between SaaS/on-prem systems, brittle custom
                  scripts, lack of visibility into integration failures.
  Motivation    : Reduce integration backlog; demonstrate architectural competence.
  Tech Savviness: Comfortable with REST APIs and basic SQL; new to OIC.
  Success Metric: # integrations delivered per sprint.

Secondary Persona: IT Manager
  Pain Points   : Governance gaps, unpredictable error storms, audit failures.
  Motivation    : Centralise integration governance; reduce on-call incidents.
  Tech Savviness: Non-coder; relies on dashboards and reports.
  Success Metric: System uptime; incident MTTR.

--- IMPLEMENTATION READINESS
Prerequisites:
  • Oracle Cloud account with OIC provisioned (trial or production)
  • Basic REST/SOAP API knowledge
  • Completed "OCI Foundations" badge (recommended)

Environment Requirements:
  • OIC 3.0 instance (Gen 3 preferred)
  • Sample REST endpoint (provided as lab utility)
  • Access to Oracle Identity Cloud Service (IDCS)

--- GTM MESSAGING
USP: Rapidly build enterprise-grade integrations on OIC without writing a single line
of middleware code.

Business Problems Solved:
  1. Fragile custom-script integrations breaking on schema changes
  2. No centralised visibility into integration health
  3. Long time-to-market for new SaaS onboarding
  4. Compliance gaps due to undocumented data flows

Learner Takeaways:
  1. Configure and test REST & SOAP adapters end-to-end
  2. Design orchestration flows with branching and looping
  3. Implement global fault handlers and notification alerts
  4. Monitor integration activity using built-in dashboards
  5. Apply OIC best practices for naming, versioning, and governance

--- COURSE COVERAGE TABLE
| Module # | Module Title | Topics | Bloom's Level | Activity Type | Duration | Source Ref |
|----------|-------------|--------|---------------|---------------|----------|------------|
| 1 | OIC Architecture & Concepts | Platform overview, tenancy, service limits | Remember | Concept + Quiz | 60 min | [URL: docs.oracle.com/oic] |
| 2 | Connection Configuration | REST, SOAP, DB adapters; security policies | Understand | Demo + Lab | 90 min | [FILE: OIC_AdminGuide.pdf] |
| 3 | Building Your First Integration | Trigger, action, map; activate & test | Apply | Lab (guided) | 90 min | [FILE: OIC_AdminGuide.pdf] |
| 4 | Orchestration Flows | Switch, for-each, parallel actions | Apply/Analyse | Lab + Scenario | 90 min | [URL: docs.oracle.com/oic] |
| 5 | Data Mapping & Transformation | XSLT mapper, JMESPATH, lookups | Analyse | Demo + Lab | 90 min | [ORACLE KNOWLEDGE BASE] |
| 6 | Error Handling & Alerts | Fault handlers, retry policies, email alerts | Analyse | Lab + Case Study | 90 min | [FILE: OIC_AdminGuide.pdf] |
| 7 | Monitoring & Observability | Activity stream, dashboards, tracking fields | Evaluate | Demo + Scenario | 60 min | [URL: docs.oracle.com/oic] |
| 8 | Governance & Best Practices | Naming conventions, versioning, export/import | Evaluate/Create | Case Study + Peer Review | 60 min | [ORACLE KNOWLEDGE BASE] |

--- CASE STUDY
Scenario: A regional bank needs to synchronise new customer records created in
Salesforce CRM with Oracle ERP Cloud within 15 minutes of account creation.

Challenge: The existing nightly batch job misses intra-day trades linked to new
accounts, causing reconciliation failures.

Solution Path (learner builds):
  Step 1 — Create a Salesforce trigger connection authenticated via OAuth 2.0.
  Step 2 — Create an Oracle ERP Cloud action connection.
  Step 3 — Build an event-driven orchestration flow (trigger: new Account created).
  Step 4 — Map Salesforce Account fields to ERP Customer schema using the visual mapper.
  Step 5 — Add a fault handler that fires an email alert on mapping failure.
  Step 6 — Activate, test with a sandbox record, and verify in Activity Stream.

Expected Outcome: Sub-minute synchronisation; zero unhandled faults.
[FILE: OIC_CaseStudy_Bank.pdf]

--- QA CHECKLIST
| # | Check | Pass/Fail |
|---|-------|-----------|
| 1 | All objectives use SMART Bloom's verbs | ✅ |
| 2 | Each module has Concept + Demo + Lab + Scenario | ✅ |
| 3 | Bloom's level matches audience (Intermediate) | ✅ |
| 4 | Prerequisites stated and honoured in Module 1 | ✅ |
| 5 | Lab-to-concept ratio ≥ 1:1 | ✅ |
| 6 | Every factual claim carries a source citation | ✅ |
| 7 | Total seat time estimated (12 hr) | ✅ |
| 8 | Modules arranged foundational → advanced | ✅ |

=== END REFERENCE SAMPLE ===
"""


# ─── CUSTOM CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter','Helvetica Neue',Arial,sans-serif; }

  .topbar { background:#1A1A2E;color:white;padding:14px 28px;border-radius:10px;
    margin-bottom:24px;display:flex;align-items:center;justify-content:space-between; }
  .topbar-left { display:flex;align-items:center;gap:14px; }
  .topbar-logo { background:#C74634;color:white;padding:6px 14px;border-radius:6px;
    font-weight:700;font-size:14px;letter-spacing:.04em; }
  .topbar-title { font-size:15px;font-weight:600;color:rgba(255,255,255,.9); }
  .topbar-sub   { font-size:12px;color:rgba(255,255,255,.55);margin-top:2px; }
  .topbar-badge { background:#C74634;color:white;padding:4px 12px;border-radius:20px;
    font-size:11px;font-weight:600;letter-spacing:.04em; }

  .section-card { background:white;border:1px solid #DDE1E7;border-radius:10px;
    padding:22px 24px;margin-bottom:18px; }
  .section-header { display:flex;align-items:center;gap:12px;padding-bottom:14px;
    margin-bottom:18px;border-bottom:1px solid #DDE1E7; }
  .section-icon { width:36px;height:36px;background:#E8F4FD;border-radius:8px;
    display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0; }
  .section-title { font-size:15px;font-weight:600;color:#1D1D1F; }
  .section-sub   { font-size:12px;color:#6B7280;margin-top:2px; }

  .gen-step { display:flex;align-items:center;gap:12px;padding:10px 14px;
    border-radius:8px;margin-bottom:8px;font-size:13px; }
  .gen-step.done    { background:#DCFCE7;color:#15803D; }
  .gen-step.active  { background:#E8F4FD;color:#005B8E; }
  .gen-step.pending { background:#F7F8FA;color:#6B7280; }
  .gen-dot { width:20px;height:20px;border-radius:50%;display:flex;align-items:center;
    justify-content:center;font-size:11px;font-weight:700;flex-shrink:0; }
  .gen-step.done .gen-dot    { background:#15803D;color:white; }
  .gen-step.active .gen-dot  { background:#005B8E;color:white; }
  .gen-step.pending .gen-dot { background:#DDE1E7;color:#6B7280; }

  .doc-wrap { background:white;border:1px solid #DDE1E7;border-radius:10px;
    overflow:hidden;margin-top:16px; }
  .doc-body { padding:28px 32px; }
  .doc-h1 { font-size:22px;font-weight:700;color:#1A1A2E;margin-bottom:4px; }
  .doc-meta-row { display:flex;gap:20px;font-size:12px;color:#6B7280;margin-bottom:18px; }

  #MainMenu,footer,header { visibility:hidden; }
  .block-container { padding-top:1.5rem!important; }
  div[data-testid="stToolbar"] { display:none; }

  .stButton>button { border-radius:7px!important;font-weight:600!important;
    font-size:13px!important;padding:8px 20px!important;transition:all .15s!important; }
  .stButton>button[kind="primary"] { background:#C74634!important;
    border-color:#C74634!important;color:white!important; }
  .stButton>button[kind="primary"]:hover { background:#A83929!important;
    border-color:#A83929!important; }
  .stTextInput>div>div>input,.stTextArea>div>div>textarea,.stSelectbox>div>div {
    border-radius:7px!important;border:1px solid #DDE1E7!important;font-size:13px!important; }
</style>
""", unsafe_allow_html=True)


# ─── SESSION STATE ─────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "step": 1,
        "course_title": "",
        "product_name": "",
        "job_roles": [],
        "custom_role": "",
        "audience_desc": "",
        "experience_level": "",
        "prereqs": "",
        "biz_outcomes": "",
        "urls": [{"type": "Product Docs", "url": ""}],
        "additional_notes": "",
        "generated": False,
        "ai_raw_output": "",
        "pdf_buf": None,
        "word_buf": None,
        "audit": None,
        "feedback_text": "",
        "show_feedback": False,
        "gen_error": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ══════════════════════════════════════════════════════════════════════════════
# BACKEND FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Reliability Audit (Enhancement 2) ─────────────────────────────────────
def perform_reliability_audit(text: str) -> dict:
    audit = {"sections": {}, "traceability_tags": 0, "source_map": defaultdict(list)}

    # Section presence
    for sec in MANDATORY_SECTIONS:
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = bool(found)

    # Traceability tags
    tags = re.findall(r"\[(FILE|URL|ORACLE KNOWLEDGE BASE)[:\s][^\]]*\]", text)
    audit["traceability_tags"] = len(tags)

    # Build source → section map
    current_section = "PREAMBLE"
    for line in text.splitlines():
        sec_match = re.match(r"---?\s*([A-Z\s]+)", line)
        if sec_match:
            current_section = sec_match.group(1).strip()
        tag_matches = re.findall(r"\[((?:FILE|URL|ORACLE KNOWLEDGE BASE)[^\]]*)\]", line)
        for tag in tag_matches:
            audit["source_map"][tag].append(current_section)

    return audit


# ── 2. URL Scraper with sub-section recursion (Enhancement 10) ───────────────
def extract_url_content(url: str, max_depth: int = 2, max_pages: int = 15) -> str:
    """
    Recursively crawls sub-links on the same domain up to max_depth levels.
    Stays within the same scheme+netloc+path prefix as the seed URL.
    """
    if not url.strip():
        return ""

    seed = url.strip()
    parsed_seed = urlparse(seed)
    base_prefix = f"{parsed_seed.scheme}://{parsed_seed.netloc}{parsed_seed.path.rstrip('/')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    visited: set = set()
    collected: list[str] = []

    def _scrape(page_url: str, depth: int):
        if depth > max_depth or page_url in visited or len(visited) >= max_pages:
            return
        visited.add(page_url)
        try:
            resp = requests.get(page_url, headers=headers, timeout=12)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            page_text = re.sub(r"\s+", " ", soup.get_text()).strip()
            collected.append(f"\n[SOURCE URL: {page_url}]\n{page_text[:8000]}\n")

            # Discover sub-links on the same domain/path prefix
            if depth < max_depth:
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    full = urljoin(page_url, href)
                    full_parsed = urlparse(full)
                    full_clean = f"{full_parsed.scheme}://{full_parsed.netloc}{full_parsed.path}"
                    if (
                        full_parsed.netloc == parsed_seed.netloc
                        and full_clean.startswith(base_prefix)
                        and full_clean not in visited
                        and "#" not in full
                    ):
                        _scrape(full_clean, depth + 1)
        except Exception as e:
            collected.append(f"\n[URL ERROR: {page_url} — {e}]\n")

    _scrape(seed, 0)
    return "".join(collected)


# ── 3. Semantic Classification Pre-processor (Enhancement 1) ─────────────────
def classify_chunks(raw_text: str) -> str:
    """
    Labels each paragraph as [INSTRUCTIONAL], [CONCEPTUAL], or [PROCEDURAL]
    using lightweight heuristics before the text is sent to the AI.
    """
    procedural_re = re.compile(
        r"\b(step \d|click|navigate|select|enter|open|run|execute|type|install"
        r"|configure|set|enable|disable|create|delete|upload|download|log in)\b",
        re.IGNORECASE,
    )
    conceptual_re = re.compile(
        r"\b(overview|introduction|concept|architecture|definition|what is"
        r"|refers to|designed to|represents|consists of|is a|is the)\b",
        re.IGNORECASE,
    )
    instructional_re = re.compile(
        r"\b(learn|understand|objective|goal|will be able to|upon completion"
        r"|by the end|outcome|skill|competency)\b",
        re.IGNORECASE,
    )

    labelled_lines = []
    for para in raw_text.split("\n"):
        para = para.strip()
        if not para:
            labelled_lines.append("")
            continue
        if procedural_re.search(para):
            labelled_lines.append(f"[PROCEDURAL] {para}")
        elif instructional_re.search(para):
            labelled_lines.append(f"[INSTRUCTIONAL] {para}")
        elif conceptual_re.search(para):
            labelled_lines.append(f"[CONCEPTUAL] {para}")
        else:
            labelled_lines.append(para)
    return "\n".join(labelled_lines)


# ── 4. File Content Extractor (PDF / PPTX / DOCX + OCR) ──────────────────────
def extract_master_content(file, ocr_enabled: bool = False) -> str:
    if file is None:
        return ""
    text = ""
    ext = file.name.split(".")[-1].lower()
    try:
        if ext == "pdf":
            f_bytes = file.read()
            with pdfplumber.open(io.BytesIO(f_bytes)) as pdf:
                for i, page in enumerate(pdf.pages):
                    p_text = page.extract_text() or ""
                    for table in page.extract_tables():
                        for row in table:
                            p_text += " | ".join(
                                [str(c) if c else "[SPANNED]" for c in row]
                            ) + "\n"
                    if ocr_enabled and (not p_text.strip() or len(p_text) < 100):
                        imgs = convert_from_bytes(f_bytes, first_page=i + 1, last_page=i + 1)
                        for img in imgs:
                            p_text += f"\n[OCR]: {pytesseract.image_to_string(img)}\n"
                    text += f"\n[FILE: {file.name} | PAGE: {i + 1}]\n{p_text}\n"

        elif ext in ["pptx", "pptm"]:
            prs = Presentation(file)
            for i, slide in enumerate(prs.slides):
                s_txt = ""
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        s_txt += shape.text + " "
                    if shape.has_table:
                        for row in shape.table.rows:
                            s_txt += (
                                " | ".join(
                                    [c.text_frame.text if not c.is_spanned else "[SPANNED]"
                                     for c in row.cells]
                                ) + "\n"
                            )
                    if ocr_enabled and shape.shape_type == 13:
                        img = Image.open(io.BytesIO(shape.image.blob))
                        s_txt += f"\n[SCREENSHOT OCR]: {pytesseract.image_to_string(img)}\n"
                text += f"\n[FILE: {file.name} | SLIDE: {i + 1}]\n{s_txt}\n"

        elif ext in ["docx", "doc"]:
            doc = DocxRead(file)
            text += "\n".join([p.text for p in doc.paragraphs])

    except Exception as e:
        st.warning(f"⚠️ Could not fully read `{file.name}`: {e}")

    # Apply semantic classification before returning
    return classify_chunks(text)


# ── 5. Markdown Table Parser helper ──────────────────────────────────────────
def parse_markdown_tables(text: str):
    """
    Returns a list of dicts: {'before': lines_before, 'headers': [...], 'rows': [[...]]}
    for each markdown table found in text.
    Also returns the text split at table boundaries for the DOCX builder.
    """
    lines = text.splitlines(keepends=True)
    segments = []   # list of ('text', str) | ('table', headers, rows)
    buf = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect header row: | col | col |
        if re.match(r"\s*\|.+\|", line):
            # Check next line is separator
            if i + 1 < len(lines) and re.match(r"\s*\|[\s\-\|:]+\|", lines[i + 1]):
                if buf:
                    segments.append(("text", "".join(buf)))
                    buf = []
                # Collect header
                headers = [c.strip() for c in line.strip().strip("|").split("|")]
                i += 2  # skip separator
                rows = []
                while i < len(lines) and re.match(r"\s*\|.+\|", lines[i]):
                    row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    rows.append(row)
                    i += 1
                segments.append(("table", headers, rows))
                continue
        buf.append(line)
        i += 1
    if buf:
        segments.append(("text", "".join(buf)))
    return segments


# ── 6. Word Builder — Enhanced (Enhancement 8) ───────────────────────────────
def _set_cell_bg(cell, hex_color: str):
    """Set table cell background colour."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def build_word(content: str, title: str) -> io.BytesIO:
    doc = DocxDocument()

    # ── Named styles ─────────────────────────────────────────────────────────
    styles = doc.styles

    # Ensure Heading 1-3 exist (they always do in a blank docx, but we tweak them)
    for lvl, sz, rgb in [(1, 16, (26, 26, 46)), (2, 13, (199, 70, 52)), (3, 11, (0, 91, 142))]:
        h = styles[f"Heading {lvl}"]
        h.font.size = Pt(sz)
        h.font.bold = True
        h.font.color.rgb = RGBColor(*rgb)

    body_style = styles["Normal"]
    body_style.font.name = "Calibri"
    body_style.font.size = Pt(10.5)

    # ── Title ─────────────────────────────────────────────────────────────────
    title_para = doc.add_heading(f"Training Design Document: {title}", level=0)
    title_para.runs[0].font.color.rgb = RGBColor(26, 26, 46)

    # ── Parse content into text/table segments ────────────────────────────────
    segments = parse_markdown_tables(content)

    for seg in segments:
        if seg[0] == "table":
            _, headers, rows = seg

            # Skip degenerate tables
            if not headers or not rows:
                continue

            col_count = len(headers)
            table = doc.add_table(rows=1 + len(rows), cols=col_count)
            table.style = "Table Grid"

            # Header row
            hdr_cells = table.rows[0].cells
            for ci, htext in enumerate(headers):
                hdr_cells[ci].text = htext
                hdr_cells[ci].paragraphs[0].runs[0].bold = True
                hdr_cells[ci].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
                _set_cell_bg(hdr_cells[ci], "1A1A2E")

            # Data rows
            for ri, row_data in enumerate(rows):
                row_cells = table.rows[ri + 1].cells
                for ci in range(col_count):
                    cell_text = row_data[ci] if ci < len(row_data) else ""
                    row_cells[ci].text = cell_text
                    if ri % 2 == 0:
                        _set_cell_bg(row_cells[ci], "F7F8FA")

            doc.add_paragraph("")  # spacing after table

        else:  # text segment
            for line in seg[1].splitlines():
                line = line.strip()
                if not line:
                    continue

                # Detect section headers like  --- COURSE OVERVIEW
                sec_match = re.match(r"---?\s*([A-Z][A-Z\s/]+)$", line)
                if sec_match:
                    doc.add_heading(sec_match.group(1).strip(), level=1)

                # Detect sub-headings (lines ending with : or all-caps short line)
                elif line.endswith(":") and len(line) < 60 and line == line.title() + ":":
                    doc.add_heading(line, level=2)

                # Bullet detection
                elif line.startswith(("- ", "• ", "* ")):
                    p = doc.add_paragraph(line[2:], style="List Bullet")
                    p.paragraph_format.left_indent = Inches(0.25)

                # Numbered list
                elif re.match(r"^\d+[\.\)]\s", line):
                    p = doc.add_paragraph(re.sub(r"^\d+[\.\)]\s", "", line), style="List Number")
                    p.paragraph_format.left_indent = Inches(0.25)

                else:
                    doc.add_paragraph(line)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ── 7. PDF Builder ────────────────────────────────────────────────────────────
def build_pdf(content: str, title: str) -> io.BytesIO:
    buf = io.BytesIO()
    doc_pdf = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "HeaderStyle", parent=styles["Heading1"],
        fontSize=13, textColor=colors.white,
        backColor=colors.HexColor("#1A1A2E"),
        alignment=TA_LEFT, spaceAfter=10, borderPadding=6,
    )
    body_style = ParagraphStyle("BodyStyle", parent=styles["Normal"], fontSize=10, leading=14)
    table_header_style = ParagraphStyle(
        "TblHdr", parent=styles["Normal"],
        fontSize=9, textColor=colors.white, fontName="Helvetica-Bold",
    )
    table_cell_style = ParagraphStyle("TblCell", parent=styles["Normal"], fontSize=9, leading=12)

    elements = [
        Paragraph(f"TRAINING DESIGN DOCUMENT: {title}", styles["Title"]),
        Spacer(1, 20),
    ]

    segments = parse_markdown_tables(content)

    for seg in segments:
        if seg[0] == "table":
            _, headers, rows = seg
            if not headers or not rows:
                continue

            tbl_data = [[Paragraph(h, table_header_style) for h in headers]]
            for row in rows:
                tbl_data.append([
                    Paragraph(row[ci] if ci < len(row) else "", table_cell_style)
                    for ci in range(len(headers))
                ])

            col_width = (landscape(A4)[0] - 60) / len(headers)
            rl_table = RLTable(tbl_data, colWidths=[col_width] * len(headers))
            rl_table.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1A1A2E")),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8FA")]),
                ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#DDE1E7")),
                ("VALIGN",      (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",  (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(rl_table)
            elements.append(Spacer(1, 10))

        else:
            for line in seg[1].splitlines():
                line = line.strip()
                if not line:
                    continue
                if any(sec in line.upper() for sec in MANDATORY_SECTIONS) and "---" in line:
                    elements.append(Spacer(1, 10))
                    elements.append(Paragraph(line.replace("-", "").strip(), header_style))
                else:
                    try:
                        elements.append(Paragraph(line, body_style))
                    except Exception:
                        clean = re.sub(r"[^\x20-\x7E]", " ", line)
                        elements.append(Paragraph(clean, body_style))

    doc_pdf.build(elements)
    buf.seek(0)
    return buf


# ── 8. Post-Generation Format Validator (Enhancement 5) ──────────────────────
def validate_format(ai_output: str, client) -> str:
    """
    Makes a second lightweight AI call to verify that all required sections
    are correctly structured and that the COURSE COVERAGE TABLE is a table,
    not prose. Returns a brief validation report (plain text).
    """
    validation_prompt = f"""
You are a Quality Reviewer for Oracle University training design documents.

Review the following document and answer ONLY in a JSON object with this exact schema:
{{
  "sections_present": {{"COURSE OVERVIEW": true/false, "PERSONA INFORMATION": true/false,
    "IMPLEMENTATION READINESS": true/false, "GTM MESSAGING": true/false,
    "COURSE COVERAGE TABLE": true/false, "CASE STUDY": true/false, "QA CHECKLIST": true/false}},
  "course_coverage_is_table": true/false,
  "qa_checklist_is_table": true/false,
  "missing_or_malformed": ["list any issues"],
  "overall": "PASS" or "FAIL"
}}

DOCUMENT TO REVIEW:
{ai_output[:6000]}
"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": validation_prompt}],
            temperature=0.0,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content
        # strip possible markdown fences
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        return data
    except Exception as e:
        return {"overall": "UNKNOWN", "error": str(e)}


# ── 9. Master Prompt Builder (Enhancements 3, 4, 6, 7) ───────────────────────
def build_master_prompt(
    product: str,
    course_title: str,
    job_roles: list,
    audience_desc: str,
    experience_level: str,
    prereqs: str,
    biz_outcomes: str,
    all_knowledge: str,
    additional_notes: str,
    feedback: str = "",
) -> str:

    feedback_block = (
        f"\nREFINEMENT FEEDBACK FROM REVIEWER:\n{feedback}\n"
        "IMPORTANT: Incorporate this feedback precisely in the regenerated document.\n"
        if feedback.strip()
        else ""
    )
    prereqs_block  = prereqs if prereqs.strip() else "None specified."
    audience_block = audience_desc if audience_desc.strip() else "Not specified — infer from job roles."

    return f"""
ACT AS: Senior Oracle Instructional Designer at Oracle University.

═══════════════════════════════════════
COURSE CONTEXT
═══════════════════════════════════════
Product Name        : {product}
Course Title        : {course_title}
Target Job Roles    : {", ".join(job_roles)}
Audience Description: {audience_block}
Experience Level    : {experience_level}
Prerequisite Skills : {prereqs_block}
Business Outcomes   : {biz_outcomes if biz_outcomes.strip() else "Not specified — derive from product and roles."}
Additional Notes    : {additional_notes if additional_notes.strip() else "None."}
{feedback_block}

═══════════════════════════════════════
SOURCE KNOWLEDGE (semantically classified — extracted from files + URLs)
Label meanings: [CONCEPTUAL]=explanatory, [PROCEDURAL]=step-by-step, [INSTRUCTIONAL]=learning objective
═══════════════════════════════════════
{all_knowledge[:20000] if all_knowledge.strip() else "[No source files or URLs provided — generate based on product knowledge and best practices.]"}

═══════════════════════════════════════
DESIGN MASTER CLASS — FULL FRAMEWORK (NON-NEGOTIABLE)
═══════════════════════════════════════
{DESIGN_MASTER_CLASS_PRINCIPLES}

═══════════════════════════════════════
SEQUENCING RULE (NON-NEGOTIABLE — Enhancement 3)
═══════════════════════════════════════
Modules MUST follow a strict prerequisite chain:
  • Module 1 is ALWAYS foundational (concepts, terminology, architecture).
  • Each subsequent module explicitly depends on the prior one.
  • Advanced design/optimisation modules come LAST.
  • Inside the COURSE COVERAGE TABLE, add a "Prerequisites" mini-column or note.
  • After the table, add one paragraph justifying the module ordering.

═══════════════════════════════════════
REFERENCE SAMPLE — MATCH THIS LEVEL OF DETAIL AND TONE
═══════════════════════════════════════
Study the sample below. Your output must match its section depth, table structure,
prose density, and citation discipline.

{SAMPLE_DESIGN_DOCUMENT}

═══════════════════════════════════════
REQUIRED OUTPUT STRUCTURE (use EXACTLY these headers)
═══════════════════════════════════════
--- COURSE OVERVIEW
--- PERSONA INFORMATION
--- IMPLEMENTATION READINESS
--- GTM MESSAGING
--- COURSE COVERAGE TABLE
--- CASE STUDY
--- QA CHECKLIST
--- TRACEABILITY MAP

Each section must be complete, detailed and grounded in the source knowledge above.

COURSE COVERAGE TABLE must be a proper markdown table with these columns:
| Module # | Module Title | Topics | Bloom's Level | Activity Type | Duration | Source Ref |

QA CHECKLIST must be a proper markdown table with columns:
| # | Check | Pass/Fail |

TRACEABILITY MAP must be a proper markdown table with columns:
| Source Tag | Document Section(s) |

Cite [FILE: filename] or [URL: link] for every factual claim.
If no source available: [ORACLE KNOWLEDGE BASE].
"""


# ══════════════════════════════════════════════════════════════════════════════
# UI — HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="topbar">
  <div class="topbar-left">
    <div class="topbar-logo">ORACLE</div>
    <div>
      <div class="topbar-title">Training Design Agent</div>
      <div class="topbar-sub">Oracle University · AI-Powered Document Generation</div>
    </div>
  </div>
  <div class="topbar-badge">AI-Powered v2</div>
</div>
""", unsafe_allow_html=True)


# ── STEPPER ────────────────────────────────────────────────────────────────────
step_labels = [
    "1 · Course Information",
    "2 · Target Audience",
    "3 · Source Content",
    "4 · Generate & Review",
]
c1, c2, c3, c4 = st.columns(4)
for col, idx, label in zip([c1, c2, c3, c4], [1, 2, 3, 4], step_labels):
    with col:
        if idx < st.session_state.step:
            st.markdown(
                f"<div style='background:#F0FDF4;border:1px solid #86EFAC;border-radius:8px;"
                f"padding:10px 14px;font-size:13px;font-weight:600;color:#15803D;"
                f"text-align:center'>✓ {label}</div>", unsafe_allow_html=True)
        elif idx == st.session_state.step:
            st.markdown(
                f"<div style='background:#E8F4FD;border:2px solid #005B8E;border-radius:8px;"
                f"padding:10px 14px;font-size:13px;font-weight:600;color:#005B8E;"
                f"text-align:center'>▶ {label}</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div style='background:#F7F8FA;border:1px solid #DDE1E7;border-radius:8px;"
                f"padding:10px 14px;font-size:13px;font-weight:500;color:#9CA3AF;"
                f"text-align:center'>{label}</div>", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom:20px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — COURSE INFORMATION
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.step == 1:
    st.markdown("""
    <div class="section-card">
      <div class="section-header">
        <div class="section-icon">📚</div>
        <div>
          <div class="section-title">Course Information</div>
          <div class="section-sub">Define the core details of the training course</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Course Title** <span style='color:#C74634'>*</span>", unsafe_allow_html=True)
    course_title = st.text_input(
        "Course Title", label_visibility="collapsed",
        placeholder="e.g. Oracle AI Agent Studio Fundamentals",
        value=st.session_state.course_title,
    )

    st.markdown("**Product Name** <span style='color:#C74634'>*</span>", unsafe_allow_html=True)
    product_name = st.text_input(
        "Product Name", label_visibility="collapsed",
        placeholder="e.g. Oracle AI Agent Studio",
        value=st.session_state.product_name,
    )

    # Enhancement 9: multi-select + free-text "other" role
    st.markdown(
        "**Associated Job Role(s)** <span style='color:#C74634'>*</span> "
        "_(select from list and/or type a custom role below)_",
        unsafe_allow_html=True,
    )
    all_roles = [
        "Solution Architect", "Developer", "Business Analyst",
        "IT Manager", "Consultant", "DBA",
        "Data Scientist", "End User", "Administrator",
    ]
    selected_roles = st.multiselect(
        "Job Roles", all_roles, label_visibility="collapsed",
        default=[r for r in st.session_state.job_roles if r in all_roles],
        placeholder="Choose one or more job roles...",
    )

    custom_role = st.text_input(
        "Custom / Other Role (optional)",
        placeholder="e.g. DevSecOps Engineer, ML Platform Lead, Cloud FinOps Analyst…",
        value=st.session_state.custom_role,
        help="Type any role not in the list above. It will be appended to your selections.",
    )

    st.divider()
    col_left, col_right = st.columns([3, 1])
    with col_left:
        st.caption("🔴 * Required fields")
    with col_right:
        if st.button("Continue to Target Audience →", type="primary", use_container_width=True):
            combined_roles = list(selected_roles)
            if custom_role.strip():
                combined_roles.append(custom_role.strip())
            if not course_title.strip():
                st.error("Course Title is required.")
            elif not product_name.strip():
                st.error("Product Name is required.")
            elif not combined_roles:
                st.error("Please select or enter at least one job role.")
            else:
                st.session_state.course_title = course_title
                st.session_state.product_name = product_name
                st.session_state.job_roles    = combined_roles
                st.session_state.custom_role  = custom_role
                st.session_state.step = 2
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — TARGET AUDIENCE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 2:
    st.markdown("""
    <div class="section-card">
      <div class="section-header">
        <div class="section-icon">👥</div>
        <div>
          <div class="section-title">Target Audience</div>
          <div class="section-sub">Describe who will take this training and their prior knowledge</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        "**Recommended Target Audience Description** "
        "<span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>",
        unsafe_allow_html=True,
    )
    audience_desc = st.text_area(
        "Audience Description", label_visibility="collapsed",
        placeholder="e.g. Oracle solution architects with 2+ years of OCI experience…",
        value=st.session_state.audience_desc, height=100,
    )

    st.markdown("**Audience Experience Level** <span style='color:#C74634'>*</span>", unsafe_allow_html=True)
    level_options = ["", "Beginner", "Intermediate", "Advanced"]
    level_labels = {
        "": "— Select Level —",
        "Beginner": "🟢 Beginner — new to the product/topic",
        "Intermediate": "🟡 Intermediate — familiar with basics, ready for configuration tasks",
        "Advanced": "🔴 Advanced — experienced, focuses on architecture & optimisation",
    }
    experience_level = st.selectbox(
        "Experience Level", level_options,
        format_func=lambda x: level_labels[x],
        label_visibility="collapsed",
        index=level_options.index(st.session_state.experience_level)
        if st.session_state.experience_level in level_options else 0,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Prerequisite Knowledge / Skills** <span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>", unsafe_allow_html=True)
        prereqs = st.text_area(
            "Prerequisites", label_visibility="collapsed",
            placeholder="e.g. Familiarity with REST APIs, basic Oracle Cloud usage…",
            value=st.session_state.prereqs, height=100,
        )
    with col2:
        st.markdown("**Business Outcomes** <span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>", unsafe_allow_html=True)
        biz_outcomes = st.text_area(
            "Business Outcomes", label_visibility="collapsed",
            placeholder="e.g. Learners will design, deploy and manage Oracle AI Agents…",
            value=st.session_state.biz_outcomes, height=100,
        )

    st.divider()
    col_back, col_fwd = st.columns(2)
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 1; st.rerun()
    with col_fwd:
        if st.button("Continue to Source Content →", type="primary", use_container_width=True):
            if not experience_level:
                st.error("Please select an Experience Level.")
            else:
                st.session_state.audience_desc    = audience_desc
                st.session_state.experience_level = experience_level
                st.session_state.prereqs          = prereqs
                st.session_state.biz_outcomes     = biz_outcomes
                st.session_state.step = 3; st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SOURCE CONTENT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 3:

    with st.sidebar:
        st.title("⚙️ Extraction Settings")
        use_ocr = st.checkbox(
            "Enable OCR for scanned PDFs / slide screenshots",
            value=False,
            help="Uses Tesseract. Slower but handles image-based documents.",
        )
        st.caption("Requires `tesseract` installed on your system.")
        st.markdown("---")
        st.caption("🔗 URL depth setting")
        url_depth = st.slider(
            "Sub-page crawl depth", min_value=0, max_value=3, value=1,
            help="0 = only the page you entered. 1 = page + direct child links. 2–3 = deeper crawl.",
        )
        url_max_pages = st.slider(
            "Max pages to crawl per URL", min_value=1, max_value=30, value=10,
        )

    st.markdown("""
    <div class="section-card">
      <div class="section-header">
        <div class="section-icon">🔗</div>
        <div>
          <div class="section-title">Documentation Links</div>
          <div class="section-sub">Oracle Docs, Confluence pages, white papers — AI will read these and follow sub-links</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    url_types = ["Product Docs", "Confluence", "White Paper", "Release Notes", "Other"]
    for i, row in enumerate(st.session_state.urls):
        col_type, col_url, col_del = st.columns([2, 5, 0.6])
        with col_type:
            new_type = st.selectbox(
                f"Type {i}", url_types,
                index=url_types.index(row["type"]) if row["type"] in url_types else 0,
                label_visibility="collapsed", key=f"url_type_{i}",
            )
        with col_url:
            new_url = st.text_input(
                f"URL {i}", value=row["url"],
                placeholder="https://docs.oracle.com/...",
                label_visibility="collapsed", key=f"url_val_{i}",
            )
        with col_del:
            if len(st.session_state.urls) > 1:
                if st.button("✕", key=f"del_url_{i}"):
                    st.session_state.urls.pop(i); st.rerun()
        st.session_state.urls[i] = {"type": new_type, "url": new_url}

    if st.button("＋ Add Another Link"):
        st.session_state.urls.append({"type": "Product Docs", "url": ""}); st.rerun()

    st.markdown("""
    <div class="section-card" style="margin-top:18px">
      <div class="section-header">
        <div class="section-icon">📤</div>
        <div>
          <div class="section-title">Upload Source Files</div>
          <div class="section-sub">PDF, PPTX, DOCX — product decks, white papers, reference guides (max 50 MB each)</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload source files", accept_multiple_files=True,
        type=["pptx", "pptm", "pdf", "docx"], label_visibility="collapsed",
    )
    if uploaded:
        for f in uploaded:
            size_mb = round(f.size / 1024 / 1024, 1)
            st.success(f"📄 **{f.name}** — {f.type.split('/')[-1].upper()} · {size_mb} MB")

    st.session_state["use_ocr"] = use_ocr if "use_ocr" in dir() else False
    st.session_state["url_depth"] = url_depth if "url_depth" in dir() else 1
    st.session_state["url_max_pages"] = url_max_pages if "url_max_pages" in dir() else 10
    st.session_state["uploaded_files_data"] = uploaded or []

    st.markdown("""
    <div class="section-card" style="margin-top:18px">
      <div class="section-header">
        <div class="section-icon">📝</div>
        <div>
          <div class="section-title">Additional Notes for the AI</div>
          <div class="section-sub">Special instructions, structural preferences, compliance requirements</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    additional_notes = st.text_area(
        "Additional Notes", label_visibility="collapsed",
        placeholder="e.g. Focus on hands-on lab activities. Include a GOV/compliance module…",
        value=st.session_state.additional_notes, height=100,
    )
    st.session_state.additional_notes = additional_notes

    st.divider()
    col_back, col_gen = st.columns(2)
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 2; st.rerun()
    with col_gen:
        if st.button("⚡ Generate Design Document", type="primary", use_container_width=True):
            st.session_state.step = 4
            st.session_state.generated = False
            st.session_state.gen_error = ""
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — GENERATE & REVIEW
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 4:

    # ── GENERATION PHASE ──────────────────────────────────────────────────────
    if not st.session_state.generated:
        st.markdown("""
        <div class="section-card">
          <div class="section-header">
            <div class="section-icon">⚡</div>
            <div>
              <div class="section-title">Generating Training Design Document</div>
              <div class="section-sub">AI agent is analysing your inputs and applying Oracle instructional design principles…</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        gen_steps = [
            "Ingesting uploaded files and documentation",
            "Scraping and parsing URL sources (with sub-link crawl)",
            "Semantic classification of source content",
            "Calibrating content depth to audience experience level",
            "Mapping content to job-role tasks and learning objectives",
            "Generating learner-centric design document via AI",
            "Validating output format (second AI pass)",
            "Building PDF and Word exports",
            "Running reliability audit on generated content",
        ]

        progress_bar = st.progress(0, text="Initialising…")
        step_placeholder = st.empty()

        def render_steps(current_idx: int):
            html = ""
            for j, s in enumerate(gen_steps):
                if j < current_idx:
                    cls, dot = "done", "✓"
                elif j == current_idx:
                    cls, dot = "active", "●"
                else:
                    cls, dot = "pending", str(j + 1)
                html += (
                    f'<div class="gen-step {cls}">'
                    f'<div class="gen-dot">{dot}</div><span>{s}</span></div>'
                )
            step_placeholder.markdown(html, unsafe_allow_html=True)

        # Step 0: Extract files
        render_steps(0); progress_bar.progress(5, text="Ingesting files…")
        use_ocr        = st.session_state.get("use_ocr", False)
        uploaded_files = st.session_state.get("uploaded_files_data", [])
        file_src = "".join([extract_master_content(f, use_ocr) for f in uploaded_files])

        # Step 1: Scrape URLs (with sub-link crawl)
        render_steps(1); progress_bar.progress(18, text="Scraping documentation URLs…")
        depth     = st.session_state.get("url_depth", 1)
        max_pages = st.session_state.get("url_max_pages", 10)
        url_src = ""
        for row in st.session_state.urls:
            if row["url"].strip():
                url_src += extract_url_content(row["url"], max_depth=depth, max_pages=max_pages)

        all_knowledge = file_src + url_src

        # Step 2: Semantic classification already done inside extract_master_content;
        #         apply to URL text now
        render_steps(2); progress_bar.progress(28, text="Classifying source content…")
        url_src_classified = classify_chunks(url_src)
        all_knowledge = file_src + url_src_classified

        # Steps 3-5: UX progress
        render_steps(3); progress_bar.progress(38, text="Analysing source content…"); time.sleep(0.4)
        render_steps(4); progress_bar.progress(50, text="Calibrating to audience level…"); time.sleep(0.3)
        render_steps(5); progress_bar.progress(62, text="Calling AI model…")

        # Step 5: Primary AI call
        try:
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            prompt = build_master_prompt(
                product=st.session_state.product_name,
                course_title=st.session_state.course_title,
                job_roles=st.session_state.job_roles,
                audience_desc=st.session_state.audience_desc,
                experience_level=st.session_state.experience_level,
                prereqs=st.session_state.prereqs,
                biz_outcomes=st.session_state.biz_outcomes,
                all_knowledge=all_knowledge,
                additional_notes=st.session_state.additional_notes,
                feedback=st.session_state.feedback_text,
            )
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=8000,
            )
            ai_output = response.choices[0].message.content
            st.session_state.ai_raw_output = ai_output

        except Exception as e:
            st.session_state.gen_error = str(e)
            st.session_state.generated = True
            st.rerun()

        # Step 6: Format validation (second AI call)
        render_steps(6); progress_bar.progress(73, text="Validating output format…")
        validation_result = validate_format(ai_output, client)
        st.session_state["validation_result"] = validation_result

        # Step 7: Build documents
        render_steps(7); progress_bar.progress(83, text="Building PDF and Word documents…")
        st.session_state.pdf_buf  = build_pdf(ai_output, st.session_state.course_title)
        st.session_state.word_buf = build_word(ai_output, st.session_state.course_title)

        # Step 8: Audit
        render_steps(8); progress_bar.progress(95, text="Running reliability audit…")
        st.session_state.audit = perform_reliability_audit(ai_output)

        progress_bar.progress(100, text="✅ Document ready!")
        render_steps(len(gen_steps))
        time.sleep(0.5)

        st.session_state.generated = True
        st.session_state.feedback_text = ""
        st.rerun()

    # ── OUTPUT PHASE ──────────────────────────────────────────────────────────
    else:
        if st.session_state.gen_error:
            st.error(f"❌ AI generation failed: {st.session_state.gen_error}")
            st.info("Check your GROQ_API_KEY in Streamlit secrets and try again.")
            if st.button("← Go Back & Retry"):
                st.session_state.step = 3
                st.session_state.generated = False
                st.session_state.gen_error = ""
                st.rerun()
            st.stop()

        title    = st.session_state.course_title
        product  = st.session_state.product_name
        level    = st.session_state.experience_level
        roles    = ", ".join(st.session_state.job_roles)
        gen_date = datetime.now().strftime("%B %d, %Y")

        col_title, col_btns = st.columns([3, 2])
        with col_title:
            st.markdown(
                f"📄 **Training Design Document** "
                f"<span style='background:#DCFCE7;color:#15803D;font-size:11px;"
                f"font-weight:600;padding:3px 10px;border-radius:20px;margin-left:6px'>"
                f"✓ Generated</span>",
                unsafe_allow_html=True,
            )
        with col_btns:
            col_fb, col_docx, col_pdf = st.columns(3)
            with col_fb:
                if st.button("💬 Feedback", use_container_width=True):
                    st.session_state.show_feedback = not st.session_state.show_feedback
                    st.rerun()
            with col_docx:
                st.download_button(
                    "⬇ DOCX", data=st.session_state.word_buf,
                    file_name=f"{title.replace(' ', '_')}_TDD.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            with col_pdf:
                st.download_button(
                    "⬇ PDF", data=st.session_state.pdf_buf,
                    file_name=f"{title.replace(' ', '_')}_TDD.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

        # ── Format Validation Panel (Enhancement 5) ───────────────────────────
        vr = st.session_state.get("validation_result", {})
        with st.expander("🔍 Format Validation Report", expanded=False):
            overall = vr.get("overall", "UNKNOWN")
            colour = "#15803D" if overall == "PASS" else "#C74634"
            st.markdown(
                f"<span style='color:{colour};font-weight:700;font-size:15px'>"
                f"Overall: {overall}</span>",
                unsafe_allow_html=True,
            )
            issues = vr.get("missing_or_malformed", [])
            if issues:
                st.markdown("**Issues found:**")
                for issue in issues:
                    st.markdown(f"- {issue}")
            else:
                st.markdown("✅ No structural issues detected.")
            if vr.get("course_coverage_is_table") is False:
                st.warning("⚠️ COURSE COVERAGE TABLE was not rendered as a markdown table — consider refining.")
            if vr.get("qa_checklist_is_table") is False:
                st.warning("⚠️ QA CHECKLIST was not rendered as a markdown table — consider refining.")

        # ── Reliability Audit with Traceability Map (Enhancement 2) ──────────
        audit = st.session_state.audit or {}
        with st.expander("📊 Reliability Audit", expanded=False):
            a_col1, a_col2 = st.columns([1, 2])
            with a_col1:
                st.metric("Traceability Tags", audit.get("traceability_tags", 0),
                          help="[FILE:…] or [URL:…] citations found in the document")
            with a_col2:
                st.markdown("**Mandatory Section Checklist**")
                for sec, found in audit.get("sections", {}).items():
                    icon   = "✅" if found else "❌"
                    colour = "#15803D" if found else "#C74634"
                    st.markdown(
                        f"<span style='color:{colour};font-weight:600'>{icon} {sec}</span>",
                        unsafe_allow_html=True,
                    )

            # Source-to-section structured table
            source_map = audit.get("source_map", {})
            if source_map:
                st.markdown("**Source → Section Traceability Map**")
                map_rows = []
                for tag, sections in source_map.items():
                    map_rows.append({"Source Tag": tag, "Document Section(s)": ", ".join(set(sections))})
                st.dataframe(map_rows, use_container_width=True)

        # ── Feedback Panel ────────────────────────────────────────────────────
        if st.session_state.show_feedback:
            st.markdown("""
            <div style='background:#FFF7ED;border:1px solid #FCD34D;border-radius:8px;
                        padding:14px 18px;margin:12px 0'>
              <strong style='font-size:13px;color:#92400E'>💬 Provide Feedback to Refine</strong><br>
              <span style='font-size:12px;color:#B45309'>
                Describe what to change — the AI will regenerate incorporating your feedback exactly.
              </span>
            </div>
            """, unsafe_allow_html=True)
            feedback = st.text_area(
                "Feedback", label_visibility="collapsed",
                placeholder="e.g. Add more hands-on lab activities. Revise Section 3 to focus on Administrator role…",
                value=st.session_state.feedback_text, height=90,
            )
            col_cancel, col_refine = st.columns(2)
            with col_cancel:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_feedback = False; st.rerun()
            with col_refine:
                if st.button("🔄 Refine Document", type="primary", use_container_width=True):
                    if feedback.strip():
                        st.session_state.feedback_text = feedback
                        st.session_state.generated = False
                        st.session_state.show_feedback = False
                        st.rerun()
                    else:
                        st.warning("Please enter feedback before refining.")

        # ── Document Preview ──────────────────────────────────────────────────
        st.markdown(f"""
        <div class="doc-wrap">
          <div class="doc-body">
            <div class="doc-h1">{title}</div>
            <div class="doc-meta-row">
              <span>📅 {gen_date}</span>
              <span>🏢 Oracle University</span>
              <span>🎯 {level}</span>
              <span>👤 {roles}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(st.session_state.ai_raw_output)

        st.divider()
        if st.button("← Start Over / New Document"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
