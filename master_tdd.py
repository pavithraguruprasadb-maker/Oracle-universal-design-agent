"""
Oracle University — Training Design Agent
Full-Stack: Multi-Step Streamlit Frontend + AI Backend (Groq / LLaMA-3.3-70B)

Install:
    pip install streamlit requests groq pdfplumber python-pptx python-docx \
                Pillow pytesseract pdf2image reportlab beautifulsoup4

Run:
    streamlit run oracle_tda_full.py
"""

# ─── IMPORTS ────────────────────────────────────────────────────────────────
import streamlit as st
import time
import io
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup

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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT
from docx import Document as DocxDocument


# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Training Design Agent | Oracle University",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── MANDATORY SECTIONS FOR AUDIT ────────────────────────────────────────────
MANDATORY_SECTIONS = [
    "COURSE OVERVIEW",
    "PERSONA INFORMATION",
    "IMPLEMENTATION READINESS",
    "GTM MESSAGING",
    "COURSE COVERAGE TABLE",
    "CASE STUDY",
    "QA CHECKLIST",
]


# ─── CUSTOM CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
  }

  .topbar {
    background: #1A1A2E; color: white;
    padding: 14px 28px; border-radius: 10px; margin-bottom: 24px;
    display: flex; align-items: center; justify-content: space-between;
  }
  .topbar-left { display: flex; align-items: center; gap: 14px; }
  .topbar-logo {
    background: #C74634; color: white;
    padding: 6px 14px; border-radius: 6px;
    font-weight: 700; font-size: 14px; letter-spacing: 0.04em;
  }
  .topbar-title  { font-size: 15px; font-weight: 600; color: rgba(255,255,255,0.9); }
  .topbar-sub    { font-size: 12px; color: rgba(255,255,255,0.55); margin-top: 2px; }
  .topbar-badge  {
    background: #C74634; color: white;
    padding: 4px 12px; border-radius: 20px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
  }

  .section-card {
    background: white; border: 1px solid #DDE1E7;
    border-radius: 10px; padding: 22px 24px; margin-bottom: 18px;
  }
  .section-header {
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 14px; margin-bottom: 18px; border-bottom: 1px solid #DDE1E7;
  }
  .section-icon {
    width: 36px; height: 36px; background: #E8F4FD;
    border-radius: 8px; display: flex; align-items: center;
    justify-content: center; font-size: 17px; flex-shrink: 0;
  }
  .section-title { font-size: 15px; font-weight: 600; color: #1D1D1F; }
  .section-sub   { font-size: 12px; color: #6B7280; margin-top: 2px; }

  .gen-step {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; border-radius: 8px;
    margin-bottom: 8px; font-size: 13px;
  }
  .gen-step.done    { background: #DCFCE7; color: #15803D; }
  .gen-step.active  { background: #E8F4FD; color: #005B8E; }
  .gen-step.pending { background: #F7F8FA; color: #6B7280; }
  .gen-dot {
    width: 20px; height: 20px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; flex-shrink: 0;
  }
  .gen-step.done .gen-dot    { background: #15803D; color: white; }
  .gen-step.active .gen-dot  { background: #005B8E; color: white; }
  .gen-step.pending .gen-dot { background: #DDE1E7; color: #6B7280; }

  .audit-pass { color: #15803D; font-weight: 600; }
  .audit-fail { color: #C74634; font-weight: 600; }

  .doc-wrap  {
    background: white; border: 1px solid #DDE1E7;
    border-radius: 10px; overflow: hidden; margin-top: 16px;
  }
  .doc-body  { padding: 28px 32px; }
  .doc-h1    { font-size: 22px; font-weight: 700; color: #1A1A2E; margin-bottom: 4px; }
  .doc-meta-row { display: flex; gap: 20px; font-size: 12px; color: #6B7280; margin-bottom: 18px; }
  .doc-section {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #C74634; margin: 20px 0 6px;
  }
  .doc-p { font-size: 14px; line-height: 1.75; color: #1D1D1F; margin-bottom: 10px; }

  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.5rem !important; }
  div[data-testid="stToolbar"] { display: none; }

  .stButton > button {
    border-radius: 7px !important; font-weight: 600 !important;
    font-size: 13px !important; padding: 8px 20px !important;
    transition: all 0.15s !important;
  }
  .stButton > button[kind="primary"] {
    background: #C74634 !important; border-color: #C74634 !important; color: white !important;
  }
  .stButton > button[kind="primary"]:hover {
    background: #A83929 !important; border-color: #A83929 !important;
  }
  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea,
  .stSelectbox > div > div {
    border-radius: 7px !important; border: 1px solid #DDE1E7 !important; font-size: 13px !important;
  }
</style>
""", unsafe_allow_html=True)


# ─── SESSION STATE ────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "step": 1,
        "course_title": "",
        "product_name": "",
        "job_roles": [],
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

# ── 1. Reliability Audit ─────────────────────────────────────────────────────
def perform_reliability_audit(text: str) -> dict:
    audit = {"sections": {}, "traceability_tags": 0}
    for sec in MANDATORY_SECTIONS:
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = bool(found)
    tags = re.findall(r"\[(FILE|URL):.*?\]", text)
    audit["traceability_tags"] = len(tags)
    return audit


# ── 2. URL Scraper ────────────────────────────────────────────────────────────
def extract_url_content(url: str) -> str:
    if not url.strip():
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url.strip(), headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text()).strip()
        return f"\n[SOURCE URL: {url}]\n{text[:15000]}\n"
    except Exception as e:
        return f"\n[URL ERROR: {url} — {e}]\n"


# ── 3. File Content Extractor (PDF / PPTX / DOCX + OCR) ──────────────────────
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
                                    [
                                        c.text_frame.text if not c.is_spanned else "[SPANNED]"
                                        for c in row.cells
                                    ]
                                )
                                + "\n"
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
    return text


# ── 4. PDF Builder ────────────────────────────────────────────────────────────
def build_pdf(content: str,    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=30, leftMargin=30,
        topMargin=30, bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Heading1"],
        fontSize=13,
        textColor=colors.white,
        backColor=colors.HexColor("#1A1A2E"),
        alignment=TA_LEFT,
        spaceAfter=10,
        borderPadding=6,
    )
    body_style = ParagraphStyle(
        "BodyStyle", parent=styles["Normal"], fontSize=10, leading=14
    )
    elements = [
        Paragraph(f"TRAINING DESIGN DOCUMENT: {title}", styles["Title"]),
        Spacer(1, 20),
    ]
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(sec in line.upper() for sec in MANDATORY_SECTIONS) and "---" in line:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(line.replace("-", ""), header_style))
        else:
            try:
                elements.append(Paragraph(line, body_style))
            except Exception:
                elements.append(Paragraph(re.sub(r"[^\x20-\x7E]", " ", line), body_style))
    doc.build(elements)
    buf.seek(0)
    return buf


# ── 5. Word Builder ───────────────────────────────────────────────────────────
def build_word(content: str, title: str) -> io.BytesIO:
    doc = DocxDocument()
    doc.add_heading(f"Training Design Document: {title}", 0)
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(sec in line.upper() for sec in MANDATORY_SECTIONS) and "---" in line:
            doc.add_heading(line.replace("-", ""), level=1)
        else:
            doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ── 6. Master Prompt Builder ──────────────────────────────────────────────────
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

    prereqs_block = prereqs if prereqs.strip() else "None specified."
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
SOURCE KNOWLEDGE (extracted from files + URLs)
═══════════════════════════════════════
{all_knowledge[:20000] if all_knowledge.strip() else "[No source files or URLs provided — generate based on product knowledge and best practices.]"}

═══════════════════════════════════════
DESIGN RULES (NON-NEGOTIABLE)
═══════════════════════════════════════
1. AUDIENCE CALIBRATION
   - Calibrate ALL content depth, vocabulary, lab complexity and assessment style to: {experience_level}
   - Beginner   → definitions, guided demos, step-by-step labs, concept-check quizzes
   - Intermediate→ configuration tasks, scenario labs, Applying/Analyzing Bloom's verbs
   - Advanced    → architecture decisions, troubleshooting, design trade-offs, Evaluating/Creating Bloom's verbs
   - Honor prerequisites: assume learners already know — {prereqs_block}

2. BALANCED MODULE MIX
   Every module MUST contain: 1× Concept, 1× Demo, 1× Hands-on Lab, 1× Scenario/Case.

3. MICROLEARNING
   Video segments: 3–7 minutes. Estimate total course seat time.

4. BLOOM'S TAXONOMY
   Use SMART verbs. Match verb level to experience level above.

5. 80/20 RULE
   Identify the 20% of skills delivering 80% of business value. State the rationale.

6. GTM MESSAGING
   Create a USP, list business problems solved, and enumerate learner takeaways.

7. TRACEABILITY
   Cite [FILE: filename] or [URL: link] for every claim drawn from source material.
   If no source material: state [ORACLE KNOWLEDGE BASE].

8. JOB-ROLE RELEVANCE
   Every learning objective must map to at least one of the stated job roles.

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

Each section must be complete, detailed and grounded in the source knowledge above.
COURSE COVERAGE TABLE must be a properly structured table with columns:
Module # | Module Title | Topics | Bloom's Level | Activity Type | Duration | Source Ref

QA CHECKLIST must verify: objectives are SMART, Bloom's alignment, audience calibration,
prerequisite alignment, lab-to-concept ratio, traceability coverage, seat-time estimate.
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
  <div class="topbar-badge">AI-Powered</div>
</div>
""", unsafe_allow_html=True)


# ── STEPPER ───────────────────────────────────────────────────────────────────
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
                f"text-align:center'>✓ {label}</div>",
                unsafe_allow_html=True,
            )
        elif idx == st.session_state.step:
            st.markdown(
                f"<div style='background:#E8F4FD;border:2px solid #005B8E;border-radius:8px;"
                f"padding:10px 14px;font-size:13px;font-weight:600;color:#005B8E;"
                f"text-align:center'>▶ {label}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='background:#F7F8FA;border:1px solid #DDE1E7;border-radius:8px;"
                f"padding:10px 14px;font-size:13px;font-weight:500;color:#9CA3AF;"
                f"text-align:center'>{label}</div>",
                unsafe_allow_html=True,
            )

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

    st.markdown(
        "**Associated Job Role(s)** <span style='color:#C74634'>*</span> _(select all that apply)_",
        unsafe_allow_html=True,
    )
    all_roles = [
        "Solution Architect", "Developer", "Business Analyst",
        "IT Manager", "Consultant", "DBA",
        "Data Scientist", "End User", "Administrator",
    ]
    selected_roles = st.multiselect(
        "Job Roles", all_roles, label_visibility="collapsed",
        default=st.session_state.job_roles,
        placeholder="Choose one or more job roles...",
    )

    st.divider()
    col_left, col_right = st.columns([3, 1])
    with col_left:
        st.caption("🔴 * Required fields")
    with col_right:
        if st.button("Continue to Target Audience →", type="primary", use_container_width=True):
            if not course_title.strip():
                st.error("Course Title is required.")
            elif not product_name.strip():
                st.error("Product Name is required.")
            elif not selected_roles:
                st.error("Please select at least one job role.")
            else:
                st.session_state.course_title = course_title
                st.session_state.product_name = product_name
                st.session_state.job_roles = selected_roles
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
        "<span style='color:#6B7280;font-weight:400;font-size:12px'>(optional — helps AI personalise content)</span>",
        unsafe_allow_html=True,
    )
    audience_desc = st.text_area(
        "Audience Description", label_visibility="collapsed",
        placeholder="e.g. Oracle solution architects with 2+ years of Oracle Cloud Infrastructure experience who are building AI-powered automation workflows...",
        value=st.session_state.audience_desc,
        height=100,
    )

    st.markdown(
        "**Audience Experience Level** <span style='color:#C74634'>*</span>",
        unsafe_allow_html=True,
    )
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
        if st.session_state.experience_level in level_options
        else 0,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            "**Prerequisite Knowledge / Skills** "
            "<span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>",
            unsafe_allow_html=True,
        )
        prereqs = st.text_area(
            "Prerequisites", label_visibility="collapsed",
            placeholder="e.g. Familiarity with REST APIs, basic Oracle Cloud usage, completed OCI Foundations...",
            value=st.session_state.prereqs,
            height=100,
        )
    with col2:
        st.markdown("**Business Outcomes** <span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>", unsafe_allow_html=True)
        biz_outcomes = st.text_area(
            "Business Outcomes", label_visibility="collapsed",
            placeholder="e.g. Learners will design, deploy and manage Oracle AI Agents in production, reducing time-to-deployment by ~40%...",
            value=st.session_state.biz_outcomes,
            height=100,
        )

    st.divider()
    col_back, col_fwd = st.columns(2)
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with col_fwd:
        if st.button("Continue to Source Content →", type="primary", use_container_width=True):
            if not experience_level:
                st.error("Please select an Experience Level — this drives how the AI calibrates content depth.")
            else:
                st.session_state.audience_desc = audience_desc
                st.session_state.experience_level = experience_level
                st.session_state.prereqs = prereqs
                st.session_state.biz_outcomes = biz_outcomes
                st.session_state.step = 3
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SOURCE CONTENT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 3:

    # ── Sidebar: OCR toggle ───────────────────────────────────────────────────
    with st.sidebar:
        st.title("⚙️ Extraction Settings")
        use_ocr = st.checkbox(
            "Enable OCR for scanned PDFs / slide screenshots",
            value=False,
            help="Uses Tesseract. Slower but handles image-based documents.",
        )
        st.caption("Requires `tesseract` installed on your system.")

    # ── Documentation URLs ────────────────────────────────────────────────────
    st.markdown("""
    <div class="section-card">
      <div class="section-header">
        <div class="section-icon">🔗</div>
        <div>
          <div class="section-title">Documentation Links</div>
          <div class="section-sub">Oracle Docs, Confluence pages, white papers, release notes — AI will read these</div>
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
                    st.session_state.urls.pop(i)
                    st.rerun()
        st.session_state.urls[i] = {"type": new_type, "url": new_url}

    if st.button("＋ Add Another Link"):
        st.session_state.urls.append({"type": "Product Docs", "url": ""})
        st.rerun()

    # ── File Upload ───────────────────────────────────────────────────────────
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
        type=["pptx", "pptm", "pdf", "docx"],
        label_visibility="collapsed",
    )
    if uploaded:
        for f in uploaded:
            size_mb = round(f.size / 1024 / 1024, 1)
            st.success(f"📄 **{f.name}** — {f.type.split('/')[-1].upper()} · {size_mb} MB")

    # Store OCR preference and files for Step 4
    st.session_state["use_ocr"] = use_ocr if "use_ocr" in dir() else False
    st.session_state["uploaded_files_data"] = uploaded or []

    # ── Additional Notes ──────────────────────────────────────────────────────
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
        placeholder="e.g. Focus on hands-on lab activities. Include scenario-based assessments. Follow the OCI learning path structure. Must include a GOV/compliance module...",
        value=st.session_state.additional_notes,
        height=100,
    )
    st.session_state.additional_notes = additional_notes

    st.divider()
    col_back, col_gen = st.columns(2)
    with col_back:
        if st.button("← Back", use_container_width=True):
            st.session_state.step = 2
            st.rerun()
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
              <div class="section-sub">AI agent is analysing your inputs and applying Oracle instructional design principles...</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        gen_steps = [
            "Ingesting uploaded files and documentation",
            "Scraping and parsing URL sources",
            "Analysing product concepts, workflows and skills",
            "Calibrating content depth to audience experience level",
            "Mapping content to job-role tasks and learning objectives",
            "Generating learner-centric design document via AI",
            "Building PDF and Word exports",
            "Running reliability audit on generated content",
        ]

        progress_bar = st.progress(0, text="Initialising...")
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

        # ── Step 0-1: Extract files ───────────────────────────────────────────
        render_steps(0)
        progress_bar.progress(5, text="Ingesting files...")

        use_ocr = st.session_state.get("use_ocr", False)
        uploaded_files = st.session_state.get("uploaded_files_data", [])
        file_src = "".join([extract_master_content(f, use_ocr) for f in uploaded_files])

        # ── Step 1-2: Scrape URLs ─────────────────────────────────────────────
        render_steps(1)
        progress_bar.progress(18, text="Scraping documentation URLs...")

        url_src = ""
        for row in st.session_state.urls:
            if row["url"].strip():
                url_src += extract_url_content(row["url"])

        all_knowledge = file_src + url_src

        # ── Step 2-5: Progress UX while AI is called ──────────────────────────
        render_steps(2); progress_bar.progress(30, text="Analysing source content...")
        time.sleep(0.5)
        render_steps(3); progress_bar.progress(45, text="Calibrating to audience level...")
        time.sleep(0.4)
        render_steps(4); progress_bar.progress(58, text="Mapping learning objectives...")
        time.sleep(0.4)
        render_steps(5); progress_bar.progress(68, text="Calling AI model...")

        # ── Step 5: AI Call ───────────────────────────────────────────────────
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

        # ── Step 6: Build documents ───────────────────────────────────────────
        render_steps(6); progress_bar.progress(82, text="Building PDF and Word documents...")
        st.session_state.pdf_buf = build_pdf(ai_output, st.session_state.course_title)
        st.session_state.word_buf = build_word(ai_output, st.session_state.course_title)

        # ── Step 7: Audit ─────────────────────────────────────────────────────
        render_steps(7); progress_bar.progress(95, text="Running reliability audit...")
        st.session_state.audit = perform_reliability_audit(ai_output)

        # ── Done ──────────────────────────────────────────────────────────────
        progress_bar.progress(100, text="✅ Document ready!")
        render_steps(len(gen_steps))
        time.sleep(0.5)

        st.session_state.generated = True
        st.session_state.feedback_text = ""   # clear after use
        st.rerun()

    # ── OUTPUT PHASE ──────────────────────────────────────────────────────────
    else:
        # ── Error state ───────────────────────────────────────────────────────
        if st.session_state.gen_error:
            st.error(f"❌ AI generation failed: {st.session_state.gen_error}")
            st.info("Check your GROQ_API_KEY in Streamlit secrets and try again.")
            if st.button("← Go Back & Retry"):
                st.session_state.step = 3
                st.session_state.generated = False
                st.session_state.gen_error = ""
                st.rerun()
            st.stop()

        # ── Toolbar ───────────────────────────────────────────────────────────
        title      = st.session_state.course_title
        product    = st.session_state.product_name
        level      = st.session_state.experience_level
        roles      = ", ".join(st.session_state.job_roles)
        gen_date   = datetime.now().strftime("%B %d, %Y")

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
                    "⬇ DOCX",
                    data=st.session_state.word_buf,
                    file_name=f"{title.replace(' ', '_')}_TDD.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            with col_pdf:
                st.download_button(
                    "⬇ PDF",
                    data=st.session_state.pdf_buf,
                    file_name=f"{title.replace(' ', '_')}_TDD.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

        # ── Reliability Audit ─────────────────────────────────────────────────
        audit = st.session_state.audit or {}
        with st.expander("📊 Reliability Audit", expanded=False):
            a_col1, a_col2 = st.columns([1, 2])
            with a_col1:
                st.metric(
                    "Traceability Tags",
                    audit.get("traceability_tags", 0),
                    help="[FILE:…] or [URL:…] citations found in the document",
                )
            with a_col2:
                st.markdown("**Mandatory Section Checklist**")
                for sec, found in audit.get("sections", {}).items():
                    icon = "✅" if found else "❌"
                    colour = "#15803D" if found else "#C74634"
                    st.markdown(
                        f"<span style='color:{colour};font-weight:600'>{icon} {sec}</span>",
                        unsafe_allow_html=True,
                    )

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
                placeholder="e.g. Add more hands-on lab activities. Revise Section 3 to focus on Administrator role. Include a governance/compliance module...",
                value=st.session_state.feedback_text,
                height=90,
            )
            col_cancel, col_refine = st.columns(2)
            with col_cancel:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_feedback = False
                    st.rerun()
            with col_refine:
                if st.button("🔄 Refine Document", type="primary", use_container_width=True):
                    if feedback.strip():
                        st.session_state.feedback_text = feedback
                        st.session_state.generated = False
                        st.session_state.show_feedback = False
                        st.rerun()
                    else:
                        st.warning("Please enter feedback before refining.")

        # ── Document Preview (renders actual AI output) ───────────────────────
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

        # Render the actual AI markdown output
        st.markdown(st.session_state.ai_raw_output)

        st.divider()
        if st.button("← Start Over / New Document"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
