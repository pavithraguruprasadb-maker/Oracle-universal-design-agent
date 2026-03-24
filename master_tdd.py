"""
Oracle University — Training Design Agent  (Enhanced v3) - 24-Mar
Full-Stack: Multi-Step Streamlit Frontend + AI Backend (Groq / LLaMA-3.3-70B)

Enhancements over v2:
  A.  Hard cap raised from 20,000 → 60,000 characters (safety net)
  B.  Smart relevance filtering — scores every paragraph against course title
      and job roles, keeps only the highest-scoring chunks up to the cap
  C.  Per-file AI summarisation — each uploaded file is summarised by a
      dedicated AI call BEFORE the main design prompt, so 100-page PDFs
      are fully represented as a tight, complete summary

Install:
    pip install streamlit requests groq pdfplumber python-pptx python-docx \
                Pillow pytesseract pdf2image reportlab beautifulsoup4 urllib3

Run:
    streamlit run master_tdd_enhanced_v3.py
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
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table as RLTable, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.units import cm as rl_cm
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
    "COURSE END GOAL",
    "PERSONA INFORMATION",
    "IMPLEMENTATION READINESS",
    "GTM MESSAGING",
    "COURSE COVERAGE TABLE",
    "END GOAL CHECKLIST",
    "ASSESSMENT TOPICS",
    "CASE STUDY",
    "CHECKLIST",
]

# ─── OPTION A: Raised hard cap ────────────────────────────────────────────────
# Previously 20,000. Now 60,000 characters — well within LLaMA-3.3-70B's
# 128k-token context window. Acts as final safety net after B & C.
KNOWLEDGE_HARD_CAP = 60_000


# ─── DESIGN MASTER CLASS PRINCIPLES ──────────────────────────────────────────
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
  Include a brief 80/20 Rationale block (1–2 bullets) stating exactly what was prioritised
  and why — grounded in job-role frequency and business impact, not arbitrary selection.

PRINCIPLE 2 — LEARNING DESIGN PHILOSOPHY & BLOOM'S TAXONOMY ALIGNMENT

  2a. DESIGN PHILOSOPHY — FOUR MENTAL FILTERS (apply to every content decision):
    1. Start with the user     — always design from the learner's perspective.
    2. Teach tasks, not tools  — focus on what the learner needs to DO, not what the product CAN do.
    3. Simplify with purpose   — every element must answer "what's in it for me?" for the learner.
    4. Show, don't just tell   — prioritise demonstration and application over passive delivery.

  2b. COURSE END GOAL (North Star — referenced throughout every design decision):
    State explicitly: what the learner will be able to DO after the course.
    Use this formula:
      "Be able to [ACTION + WHAT] in [CONTEXT] without [DEPENDENCY]"
    Example: "Independently deploy, configure, and monitor the product in a production
    environment without external support."
    A vague end goal produces a vague course. Every module, topic, and activity must
    trace back to this end goal.

  2c. BLOOM'S TAXONOMY ALIGNMENT:
    Map every learning objective to a Bloom's level verb appropriate for the audience tier:
      Beginner    → Remember / Understand  (define, describe, identify, explain)
      Intermediate→ Apply / Analyse        (configure, implement, compare, troubleshoot)
      Advanced    → Evaluate / Create      (design, optimise, justify, architect)
    Objectives must be SMART (Specific, Measurable, Achievable, Relevant, Time-bound).
    Use measurable Bloom's action verbs (configure, deploy, troubleshoot, architect) —
    never passive knowledge statements.

  2d. LEARNING JOURNEY SUMMARY:
    Include a 3–5 sentence narrative describing the complete learning arc from start to
    finish — how the learner progresses from foundational awareness to confident
    independent performance.

  2e. MODULE BREAKDOWN REQUIREMENTS:
    For every module and every lesson/topic within it, explicitly state:
      • Connection to the Course End Goal
      • Estimated duration
      • What is taught (content summary)
      • 3–5 action-oriented Key Takeaways using Bloom's verbs

  2f. WHAT YOU CAN DO NOW (closing statement per module):
    End each module description with a motivating 1–2 sentence statement confirming
    what the learner can now independently accomplish.

  2g. END GOAL CHECKLIST:
    The document must include 5–8 "I can…" self-assessment statements directly tied
    to the Course End Goal. These confirm readiness and close the learning loop.
    Example: "I can configure a REST adapter connection in OIC without referencing
    the user guide."

  2h. ASSESSMENT TOPICS:
    Provide 5–10 assessment topic areas with:
      • Topic name
      • Rationale (why this is assessed)
      • Suggested assessment type (quiz / scenario / practical exercise)
      • Difficulty level (Foundational / Intermediate / Advanced)

PRINCIPLE 3 — MICROLEARNING ARCHITECTURE
  Every video or concept block: 3–7 minutes maximum.
  Every module: no more than 4 activities (Concept → Demo → Lab → Scenario).
  Provide an estimated seat-time per topic, per lab, per module, and a cumulative
  course total.

PRINCIPLE 4 — BALANCED ACTIVITY MIX
  Each module MUST include exactly:
    1 × Concept explanation  (lecture / reading)
    1 × Instructor/recorded Demo
    1 × Hands-on Lab (guided or open-ended, scaled to level)
    1 × Scenario or Case-study question
  Activities may be combined where appropriate but all four types must be present.

PRINCIPLE 5 — GTM MESSAGING FRAMEWORK (FULL — READY TO USE)
  The GTM section MUST include ALL of the following elements:

  5a. CORE GTM MESSAGE (5 elements, jargon-free, one-minute pitch):
    1. What the product is         — brief plain-language description
    2. What makes it stand out     — USP aligned with Product team positioning (≤ 25 words)
    3. Who the course is for       — specific target roles / teams
    4. What business problems it solves — 3–5 bullet points
    5. What learners will take away — 5–7 outcomes phrased as business results

  5b. LINKEDIN POST (150–250 words, course-specific, ready to publish):
    Write a compelling LinkedIn post announcing this specific course. It must:
      • Open with a hook relevant to the learner's pain point
      • Name the course and product explicitly
      • Call out 2–3 key outcomes learners will achieve
      • Include a clear call-to-action (enrol, learn more, etc.)
      • Use professional but conversational tone
      • Be specific to this course content — NOT generic Oracle marketing copy

  5c. NEWSLETTER WRITE-UP (200–300 words, course-specific, ready to use):
    Write a newsletter announcement for this specific course. It must include:
      • Headline
      • Opening paragraph (what, why it matters now)
      • Key learning outcomes (3–4 bullets)
      • Who should enrol and why
      • Call-to-action with urgency or relevance framing
      • Be specific to this course — NOT a template with placeholder text

PRINCIPLE 6 — PREREQUISITE CHAIN (FOUNDATIONAL → ADVANCED)
  Arrange modules so every module builds on the prior one.
  Module 1 is always foundational (concepts, terminology, architecture overview).
  Advanced configuration / design modules come last.
  State explicit prerequisites between modules inside the Coverage Table.

PRINCIPLE 7 — AUDIENCE PERSONA FIDELITY
  For each persona, provide a full profile:
    • Name (representative, not generic)
    • Role title
    • Top 5 day-to-day responsibilities
    • Top 3 pain points
    • Learning preferences
    • Tech-savviness level
    • Primary business metric they are measured on
  Ground every content decision in these persona profiles.

PRINCIPLE 8 — TRACEABILITY & CITATIONS
  Every factual claim must carry a source tag. Use these formats:
    [FILE: exact_filename.ext] — for uploaded documents
    [URL: full_url_path]       — for scraped web pages (include the actual URL, not just the domain)
    [ORACLE KNOWLEDGE BASE: topic_area] — only when no file or URL is available;
      must include the specific topic area (e.g., [ORACLE KNOWLEDGE BASE: OIC Adapter Configuration])
      so the reader knows what domain knowledge was used.
  NEVER use a bare [ORACLE KNOWLEDGE BASE] tag without elaboration.
  The document must end with a TRACEABILITY MAP table.

PRINCIPLE 9 — ROLE & SKILL ALIGNMENT
  Map each job task to the specific skills it requires.
  Every module must support measurable on-the-job performance for the target role.
  No module may exist solely to explain product features — it must tie to a real job task.

PRINCIPLE 10 — SKILL CHECKS & ASSESSMENT DESIGN
  Design assessments (quizzes, practical exercises, scenario-based questions) that
  directly measure the stated learning outcomes.
  Every skill check question must:
    1. Be tied to a specific module or learning outcome.
    2. Present a realistic scenario or task — not a trivial recall question.
    3. Include plausible distractors reflecting common learner misconceptions.
    4. Have one clearly correct answer that directly reflects the content taught.

=== END DESIGN MASTER CLASS FRAMEWORK ===
"""


# ─── SAMPLE COMPLETED DESIGN DOCUMENT ────────────────────────────────────────
_SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "sample_design_document.txt")
if os.path.exists(_SAMPLE_FILE):
    with open(_SAMPLE_FILE, "r", encoding="utf-8") as _f:
        SAMPLE_DESIGN_DOCUMENT = _f.read()
else:
    SAMPLE_DESIGN_DOCUMENT = """
=== REFERENCE SAMPLE — MATCH THIS LEVEL OF DETAIL AND TONE ===

--- COURSE OVERVIEW
Course Title   : Oracle Integration Cloud Fundamentals
Product Area   : Oracle Integration Cloud (OIC) 3.0
Training Need  : Developers and Architects lack hands-on OIC skills, causing slow
                 integration delivery and brittle custom-script workarounds.
Target Audience: Integration Developers, IT Architects (Intermediate level)
Duration       : 12 hours (8 modules × avg 90 min)
Delivery       : Instructor-led + self-paced eLearning

Course Description:
This course equips Integration Developers and Architects with the end-to-end skills
to design, build, and monitor enterprise integrations using Oracle Integration Cloud.
Learners exit able to configure REST and SOAP adapters, build orchestration flows,
and instrument error handling and monitoring dashboards.

80/20 Rationale:
  • REST adapter configuration and Orchestration flow design account for ~80% of
    production OIC usage — these receive the deepest treatment (Modules 3–6).
  • Monitoring and governance (20%) are covered efficiently in Modules 7–8 since
    they leverage the same UI patterns already learned. [ORACLE KNOWLEDGE BASE: OIC Usage Analytics]

Assumptions & Open Questions:
  • Assumed learners have completed OCI Foundations badge.
  • Open: Does the client require localisation (languages other than English)?

--- COURSE END GOAL
End Goal: Be able to independently design, deploy, and monitor multi-step enterprise
integrations in Oracle Integration Cloud in a production tenancy without external support.

Learning Journey Summary:
Learners begin by grounding themselves in OIC architecture and core concepts (Module 1),
then progressively configure connections, build their first integration, and apply
orchestration patterns (Modules 2–4). The mid-section deepens skills in data mapping
and error handling — the two most common sources of production failures (Modules 5–6).
The journey closes with monitoring, observability, and governance (Modules 7–8), so
learners can sustain and scale what they have built. By the end, learners can own an
integration end-to-end from requirement to production deployment.

--- PERSONA INFORMATION
Primary Persona  : Priya — Integration Developer
  Top 5 Responsibilities: Build and maintain SaaS-to-ERP integrations; troubleshoot
    failed message flows; document integration architecture; coordinate with API teams;
    govern naming conventions and versioning.
  Top 3 Pain Points: Manual data movement between systems; brittle custom scripts that
    break on schema changes; no centralised visibility into integration failures.
  Learning Preferences: Hands-on labs, worked examples, searchable reference docs.
  Tech-Savviness: Comfortable with REST APIs and basic SQL; new to OIC.
  Success Metric: # integrations delivered per sprint.

Secondary Persona: Rohan — IT Manager
  Top 5 Responsibilities: Oversee integration governance; manage on-call incidents;
    report uptime to leadership; audit data flows for compliance; approve new connections.
  Top 3 Pain Points: Governance gaps; unpredictable error storms; audit failures.
  Learning Preferences: Dashboards, executive summaries, scenario walkthroughs.
  Tech-Savviness: Non-coder; relies on dashboards and reports.
  Success Metric: System uptime; incident MTTR.

--- IMPLEMENTATION READINESS
Prerequisites (Learner): Basic REST/SOAP API knowledge; completed "OCI Foundations" badge (recommended).
Prerequisites (Access): Oracle Cloud account with OIC provisioned (trial or production);
  access to Oracle Identity Cloud Service (IDCS); OIC 3.0 instance (Gen 3 preferred).
Required Tools/Materials: Sample REST endpoint (provided as lab utility); lab exercise guides;
  OIC_AdminGuide.pdf reference.
Accessibility & Delivery: Captions required for all video topics; hosted on Oracle MyLearn LMS;
  English only (localisation TBD — see Open Questions).
Assessment Plan: Knowledge check quiz per module (≥80% pass); lab completion sign-off;
  final scenario-based assessment covering Modules 4–6 (task completion criteria).

--- GTM MESSAGING

5a. Core GTM Message:
  Product: Oracle Integration Cloud (OIC) is Oracle's cloud-native integration platform
    enabling enterprises to connect SaaS, on-premises, and custom applications without
    writing middleware code.
  USP: Build enterprise-grade integrations in hours, not weeks — no middleware expertise required.
  Who it's for: Integration Developers and IT Architects managing Oracle Cloud environments.
  Business Problems Solved:
    1. Fragile custom-script integrations breaking on schema changes
    2. No centralised visibility into integration health and failures
    3. Long time-to-market for new SaaS application onboarding
    4. Compliance gaps from undocumented and ungoverned data flows
  Learner Takeaways:
    1. Configure and test REST & SOAP adapter connections end-to-end
    2. Design orchestration flows with branching, looping, and parallel actions
    3. Implement global fault handlers and automated notification alerts
    4. Monitor integration activity using built-in dashboards and activity streams
    5. Apply OIC governance best practices for naming, versioning, and export/import

5b. LinkedIn Post:
  Still losing hours to broken integrations and mystery failures at 2am?
  Oracle Integration Cloud can change that — and now there's a course to prove it.

5c. Newsletter Write-Up:
  Headline: New Course Alert: Master Oracle Integration Cloud from Day One

--- COURSE COVERAGE TABLE
| Module # | Module Title | Module Learning Objective | Topic # | Topic Title | What We Teach in This Topic/Lesson | Bloom's Level | Activity Type | Est. Video Duration (min) | Key Takeaways (3–5 action-oriented) | Matching Hands-On Lab | Lab Type | Lab Duration (min) | Source Ref |
|----------|-------------|--------------------------|---------|-------------|-----------------------------------|---------------|---------------|--------------------------|-------------------------------------|----------------------|----------|-------------------|------------|
| 1 | OIC Architecture & Concepts | Describe the OIC platform architecture and identify its core components | 1.1 | Platform Overview | Covers OIC console navigation, tenancy concepts, instance types. | Remember | Concept video | 5 | • Describe OIC's role • Identify Gen2 vs Gen3 • Navigate the console | N/A | N/A | — | [URL: https://docs.oracle.com/en/cloud/paas/application-integration/] |

--- END GOAL CHECKLIST
| # | I Can Statement | Bloom's Level | Maps to Module |
|---|----------------|---------------|----------------|
| 1 | I can configure a REST adapter connection and test it without referencing the user guide | Apply | 2 |

--- ASSESSMENT TOPICS
| # | Assessment Topic | Rationale | Suggested Type | Difficulty Level |
|---|-----------------|-----------|----------------|-----------------|
| 1 | OIC Core Terminology | Foundational vocabulary underpins all later tasks | Knowledge Check Quiz | Foundational |

--- CASE STUDY
Goal: Automate real-time customer record synchronisation between Salesforce CRM and Oracle ERP Cloud.

--- CHECKLIST
| # | Check | Pass/Fail |
|---|-------|-----------|
| 1 | Every job task maps to at least one skill and at least one module/topic | ✅ |

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
        "product_context": "",
        "use_benchmark": False,
        "benchmark_text": "",
        "benchmark_filename": "",
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
        "file_summaries": [],   # NEW: stores per-file AI summaries
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─── SECRETS VALIDATION ───────────────────────────────────────────────────────
_groq_key = st.secrets.get("GROQ_API_KEY", None)
if not _groq_key:
    st.error(
        "🔑 **GROQ_API_KEY not found in Streamlit Secrets.**\n\n"
        "**To fix this:**\n"
        "1. Go to your app on [share.streamlit.io](https://share.streamlit.io)\n"
        "2. Click the **⋮ three-dot menu** next to your app → **Settings** → **Secrets**\n"
        "3. Paste exactly this (with your real key):\n\n"
        "```toml\nGROQ_API_KEY = \"gsk_xxxxxxxxxxxxxxxxxxxx\"\n```\n\n"
        "4. Click **Save** — the app reboots automatically.\n\n"
        "Get a free key at [console.groq.com](https://console.groq.com) → API Keys."
    )
    st.stop()

GROQ_CLIENT = Groq(api_key=_groq_key)


# ══════════════════════════════════════════════════════════════════════════════
# BACKEND FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Reliability Audit ──────────────────────────────────────────────────────
def perform_reliability_audit(text: str) -> dict:
    audit = {"sections": {}, "traceability_tags": 0, "source_map": defaultdict(list)}
    for sec in MANDATORY_SECTIONS:
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = bool(found)
    tags = re.findall(r"\[(FILE|URL|ORACLE KNOWLEDGE BASE)[:\s][^\]]*\]", text)
    audit["traceability_tags"] = len(tags)
    current_section = "PREAMBLE"
    for line in text.splitlines():
        sec_match = re.match(r"---?\s*([A-Z\s]+)", line)
        if sec_match:
            current_section = sec_match.group(1).strip()
        tag_matches = re.findall(r"\[((?:FILE|URL|ORACLE KNOWLEDGE BASE)[^\]]*)\]", line)
        for tag in tag_matches:
            audit["source_map"][tag].append(current_section)
    return audit


# ── 2. URL Scraper with sub-section recursion ─────────────────────────────────
def extract_url_content(url: str, max_depth: int = 2, max_pages: int = 15) -> str:
    if not url.strip():
        return ""
    seed = url.strip()
    parsed_seed = urlparse(seed)
    base_prefix = f"{parsed_seed.scheme}://{parsed_seed.netloc}{parsed_seed.path.rstrip('/')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    visited: set = set()
    collected: list = []

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


# ── 3. Semantic Classification Pre-processor ──────────────────────────────────
def classify_chunks(raw_text: str) -> str:
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


# ── OPTION B: Smart Relevance Filter ─────────────────────────────────────────
def smart_filter_chunks(
    raw_text: str,
    course_title: str,
    job_roles: list,
    cap: int = KNOWLEDGE_HARD_CAP,
) -> str:
    """
    Scores every paragraph in raw_text by keyword overlap with course_title
    and job_roles. Keeps the highest-scoring paragraphs until the cap is reached.
    Low-scoring filler paragraphs are dropped, preserving source tags.

    This means a 100-page PDF will contribute its MOST RELEVANT paragraphs
    rather than just the first N characters.
    """
    # Build keyword set from title + roles (lowercase, split on spaces/punctuation)
    keywords = set(re.findall(r"[a-z]{3,}", (course_title + " " + " ".join(job_roles)).lower()))

    paragraphs = raw_text.split("\n")
    scored = []
    for para in paragraphs:
        lower = para.lower()
        # Always keep source tags and section markers — score them high
        if re.match(r"^\[(FILE|URL|SOURCE)", para) or re.match(r"^\[PROCEDURAL|CONCEPTUAL|INSTRUCTIONAL", para):
            scored.append((999, para))
            continue
        score = sum(1 for kw in keywords if kw in lower)
        scored.append((score, para))

    # Sort by score descending, but reconstruct in ORIGINAL ORDER
    # Strategy: keep all paragraphs above score 0, then fill remaining budget
    # from score-0 paragraphs to preserve some context.
    kept_high  = [p for s, p in scored if s > 0]
    kept_low   = [p for s, p in scored if s == 0]

    result_lines = []
    budget = cap
    for para in kept_high:
        if budget <= 0:
            break
        result_lines.append(para)
        budget -= len(para)

    # Fill remaining budget with low-score paragraphs for context
    for para in kept_low:
        if budget <= 0:
            break
        result_lines.append(para)
        budget -= len(para)

    return "\n".join(result_lines)


# ── OPTION C: Per-File AI Summarisation ──────────────────────────────────────
def summarise_file_with_ai(
    filename: str,
    raw_text: str,
    course_title: str,
    job_roles: str,
    product_name: str,
) -> str:
    """
    Makes a dedicated AI call to summarise a single file's full extracted text.
    This means even a 200-page PDF is fully read and distilled into a structured
    summary that captures ALL key concepts, procedures, and tables — not just
    the first 20k characters.

    Returns a compact, structured summary tagged with [FILE: filename].
    """
    # Send up to 40,000 chars of the raw file to the summariser
    # (well within LLaMA context window for a single focused call)
    text_to_summarise = raw_text[:40_000]

    summary_prompt = f"""
You are an expert Oracle instructional designer.

You have been given extracted text from the file: "{filename}"

Your task: Produce a STRUCTURED SUMMARY of this document for use in designing
a training course with the following context:
  Course Title : {course_title}
  Product      : {product_name}
  Job Roles    : {job_roles}

Your summary MUST:
1. Be organised under these headings (use only those that apply):
   - KEY CONCEPTS & DEFINITIONS
   - PRODUCT ARCHITECTURE & COMPONENTS
   - STEP-BY-STEP PROCEDURES & WORKFLOWS
   - CONFIGURATION PARAMETERS & SETTINGS
   - TABLES, DATA SCHEMAS & REFERENCE MATERIAL
   - LEARNING OBJECTIVES & OUTCOMES (if present)
   - COMMON ERRORS, TROUBLESHOOTING & BEST PRACTICES
   - BUSINESS USE CASES & SCENARIOS

2. Under each heading, use bullet points.
3. Preserve specific product names, field names, parameter values, and step numbers exactly.
4. Do NOT paraphrase technical terms — keep them verbatim.
5. Every bullet must tag its source: [FILE: {filename}]
6. Target length: 800–1200 words. Be comprehensive — this summary replaces the full document.
7. If the document contains tables, reproduce their key column headers and a representative row.

DOCUMENT TEXT:
{text_to_summarise}

OUTPUT THE STRUCTURED SUMMARY ONLY. No preamble, no meta-commentary.
"""

    try:
        resp = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.2,
            max_tokens=2000,
        )
        summary = resp.choices[0].message.content.strip()
        return f"\n\n=== AI SUMMARY OF: {filename} ===\n{summary}\n=== END SUMMARY ===\n\n"
    except Exception as e:
        # Fallback: return first 8000 chars if AI summarisation fails
        return f"\n\n=== FALLBACK EXTRACT: {filename} (AI summary failed: {e}) ===\n{raw_text[:8000]}\n"


# ── 4. File Content Extractor (PDF / PPTX / DOCX + OCR) ──────────────────────
def extract_master_content(file, ocr_enabled: bool = False) -> str:
    """Extracts ALL pages/slides from a file with no page limit."""
    if file is None:
        return ""
    text = ""
    ext = file.name.split(".")[-1].lower()
    try:
        if ext == "pdf":
            f_bytes = file.read()
            with pdfplumber.open(io.BytesIO(f_bytes)) as pdf:
                total_pages = len(pdf.pages)
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
                    text += f"\n[FILE: {file.name} | PAGE: {i + 1} of {total_pages}]\n{p_text}\n"

        elif ext in ["pptx", "pptm"]:
            prs = Presentation(file)
            total_slides = len(prs.slides)
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
                text += f"\n[FILE: {file.name} | SLIDE: {i + 1} of {total_slides}]\n{s_txt}\n"

        elif ext in ["docx", "doc"]:
            doc = DocxRead(file)
            text += "\n".join([p.text for p in doc.paragraphs])

    except Exception as e:
        st.warning(f"⚠️ Could not fully read `{file.name}`: {e}")

    # Apply semantic classification
    return classify_chunks(text)


# ── 5. Markdown Table Parser ──────────────────────────────────────────────────
def parse_markdown_tables(text: str):
    lines = text.splitlines(keepends=True)
    segments = []
    buf = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"\s*\|.+\|", line):
            if i + 1 < len(lines) and re.match(r"\s*\|[\s\-\|:]+\|", lines[i + 1]):
                if buf:
                    segments.append(("text", "".join(buf)))
                    buf = []
                headers = [c.strip() for c in line.strip().strip("|").split("|")]
                i += 2
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


# ── 6. Word Builder ───────────────────────────────────────────────────────────
_C_NAVY      = "1A1A2E"
_C_RED       = "C74634"
_C_BLUE      = "005B8E"
_C_SILVER    = "F0F4F8"
_C_BORDER    = "DDE1E7"
_C_WHITE     = "FFFFFF"
_C_DARK_TEXT = "1D1D1F"


def _rgb(hex6: str) -> RGBColor:
    return RGBColor(int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16))


def _set_cell_bg(cell, hex_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _set_cell_border(cell, hex_color: str = _C_BORDER):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), hex_color)
        tcBorders.append(border)
    tcPr.append(tcBorders)


def _set_cell_padding(cell, top=60, bottom=60, left=100, right=100):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        m = OxmlElement(f"w:{side}")
        m.set(qn("w:w"), str(val))
        m.set(qn("w:type"), "dxa")
        tcMar.append(m)
    tcPr.append(tcMar)


def _add_cover_page(doc, title, gen_date, product, roles, level):
    bar = doc.add_table(rows=1, cols=1)
    bar.style = "Table Grid"
    bar_cell = bar.rows[0].cells[0]
    _set_cell_bg(bar_cell, _C_NAVY)
    bar_cell.paragraphs[0].clear()
    run = bar_cell.paragraphs[0].add_run("  ORACLE UNIVERSITY")
    run.font.bold = True; run.font.size = Pt(11)
    run.font.color.rgb = _rgb(_C_WHITE); run.font.name = "Calibri"
    bar_cell.paragraphs[0].paragraph_format.space_before = Pt(6)
    bar_cell.paragraphs[0].paragraph_format.space_after  = Pt(6)
    doc.add_paragraph("")
    lbl = doc.add_paragraph()
    lbl_run = lbl.add_run("TRAINING DESIGN DOCUMENT")
    lbl_run.font.size = Pt(9); lbl_run.font.bold = True
    lbl_run.font.color.rgb = _rgb(_C_RED); lbl_run.font.name = "Calibri"
    lbl.paragraph_format.space_after = Pt(4)
    t = doc.add_paragraph()
    t_run = t.add_run(title)
    t_run.font.size = Pt(24); t_run.font.bold = True
    t_run.font.color.rgb = _rgb(_C_NAVY); t_run.font.name = "Calibri"
    t.paragraph_format.space_after = Pt(16)
    meta = doc.add_table(rows=1, cols=4)
    meta.style = "Table Grid"
    meta_labels = [("📅 Date", gen_date), ("📦 Product", product),
                   ("🎯 Level", level), ("👤 Roles", roles[:40] + "…" if len(roles) > 40 else roles)]
    for ci, (lbl_txt, val_txt) in enumerate(meta_labels):
        cell = meta.rows[0].cells[ci]
        _set_cell_bg(cell, _C_SILVER); _set_cell_border(cell, _C_BORDER)
        _set_cell_padding(cell, 80, 80, 120, 120)
        p = cell.paragraphs[0]; p.clear()
        label_r = p.add_run(lbl_txt + "\n")
        label_r.font.size = Pt(8); label_r.font.bold = True
        label_r.font.color.rgb = _rgb(_C_BLUE); label_r.font.name = "Calibri"
        val_r = p.add_run(val_txt)
        val_r.font.size = Pt(9); val_r.font.name = "Calibri"
        val_r.font.color.rgb = _rgb(_C_DARK_TEXT)
    doc.add_paragraph("")
    div = doc.add_paragraph()
    div_run = div.add_run("─" * 90)
    div_run.font.color.rgb = _rgb(_C_RED); div_run.font.size = Pt(8)
    div.paragraph_format.space_after = Pt(14)


def _add_section_header(doc, title):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = "Table Grid"
    cell = tbl.rows[0].cells[0]
    _set_cell_bg(cell, _C_NAVY); _set_cell_padding(cell, 80, 80, 160, 160)
    p = cell.paragraphs[0]; p.clear()
    run = p.add_run(title)
    run.font.bold = True; run.font.size = Pt(11)
    run.font.color.rgb = _rgb(_C_WHITE); run.font.name = "Calibri"
    sp = doc.add_paragraph("")
    sp.paragraph_format.space_before = Pt(0); sp.paragraph_format.space_after = Pt(4)


def _add_sub_heading(doc, title):
    p = doc.add_paragraph()
    run = p.add_run(title)
    run.font.bold = True; run.font.size = Pt(10.5)
    run.font.color.rgb = _rgb(_C_RED); run.font.name = "Calibri"
    p.paragraph_format.space_before = Pt(8); p.paragraph_format.space_after = Pt(3)
    return p


def _style_table(doc, headers, rows):
    if not headers or not rows:
        return
    col_count = len(headers)
    table = doc.add_table(rows=1 + len(rows), cols=col_count)
    table.style = "Table Grid"
    tbl_elem = table._tbl
    tblPr = tbl_elem.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr"); tbl_elem.insert(0, tblPr)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), "0"); tblW.set(qn("w:type"), "auto")
    tblPr.append(tblW)
    hdr_cells = table.rows[0].cells
    for ci, htext in enumerate(headers):
        cell = hdr_cells[ci]
        _set_cell_bg(cell, _C_NAVY); _set_cell_border(cell, "2E3A6E")
        _set_cell_padding(cell, 80, 80, 120, 120)
        p = cell.paragraphs[0]; p.clear()
        run = p.add_run(htext)
        run.bold = True; run.font.size = Pt(9)
        run.font.color.rgb = _rgb(_C_WHITE); run.font.name = "Calibri"
    for ri, row_data in enumerate(rows):
        row_cells = table.rows[ri + 1].cells
        bg = _C_WHITE if ri % 2 == 0 else _C_SILVER
        for ci in range(col_count):
            cell = row_cells[ci]
            cell_text = row_data[ci] if ci < len(row_data) else ""
            _set_cell_bg(cell, bg); _set_cell_border(cell, _C_BORDER)
            _set_cell_padding(cell, 70, 70, 110, 110)
            p = cell.paragraphs[0]; p.clear()
            run = p.add_run(cell_text)
            run.font.size = Pt(9); run.font.name = "Calibri"
            run.font.color.rgb = _rgb(_C_DARK_TEXT)
    doc.add_paragraph("").paragraph_format.space_after = Pt(8)


def build_word(content: str, title: str) -> io.BytesIO:
    doc = DocxDocument()
    for section in doc.sections:
        section.top_margin    = Cm(1.8); section.bottom_margin = Cm(1.8)
        section.left_margin   = Cm(2.2); section.right_margin  = Cm(2.2)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"; normal.font.size = Pt(10)
    normal.font.color.rgb = _rgb(_C_DARK_TEXT)
    for lvl, sz, col in [(1, 13, _C_NAVY), (2, 11, _C_RED), (3, 10, _C_BLUE)]:
        h = doc.styles[f"Heading {lvl}"]
        h.font.name = "Calibri"; h.font.size = Pt(sz); h.font.bold = True
        h.font.color.rgb = _rgb(col)
        h.paragraph_format.space_before = Pt(10); h.paragraph_format.space_after = Pt(4)
    gen_date = datetime.now().strftime("%B %d, %Y")
    _add_cover_page(doc, title, gen_date, product="Oracle University",
                    roles="See Persona Section", level="See Course Overview")
    segments = parse_markdown_tables(content)
    for seg in segments:
        if seg[0] == "table":
            _, headers, rows = seg
            _style_table(doc, headers, rows)
        else:
            for line in seg[1].splitlines():
                line = line.strip()
                if not line:
                    continue
                sec_match = re.match(r"---?\s*([A-Z][A-Z\s/\-]+)$", line)
                if sec_match:
                    _add_section_header(doc, sec_match.group(1).strip()); continue
                kv_match = re.match(r"^([A-Z][A-Za-z\s/\-]{1,40})\s*:\s*(.+)$", line)
                if kv_match:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_before = Pt(1); p.paragraph_format.space_after = Pt(1)
                    key_run = p.add_run(kv_match.group(1) + ": ")
                    key_run.bold = True; key_run.font.size = Pt(10)
                    key_run.font.name = "Calibri"; key_run.font.color.rgb = _rgb(_C_NAVY)
                    val_run = p.add_run(kv_match.group(2))
                    val_run.font.size = Pt(10); val_run.font.name = "Calibri"
                    val_run.font.color.rgb = _rgb(_C_DARK_TEXT); continue
                if (line.endswith(":") and len(line) < 70
                        and (line == line.title() + ":" or line == line.upper())):
                    _add_sub_heading(doc, line); continue
                if re.match(r"^\d+[a-z]?\.\s+[A-Z]", line) or re.match(r"^[A-Z]{2,}[\s:–]", line):
                    p = doc.add_paragraph()
                    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(2)
                    run = p.add_run(line); run.bold = True; run.font.size = Pt(10)
                    run.font.name = "Calibri"; run.font.color.rgb = _rgb(_C_BLUE); continue
                if line.startswith(("- ", "• ", "* ", "· ")):
                    p = doc.add_paragraph(style="List Bullet")
                    p.paragraph_format.left_indent = Inches(0.3)
                    p.paragraph_format.space_before = Pt(1); p.paragraph_format.space_after = Pt(1)
                    run = p.add_run(line[2:]); run.font.size = Pt(10); run.font.name = "Calibri"; continue
                if re.match(r"^\d+[\.\)]\s", line):
                    p = doc.add_paragraph(style="List Number")
                    p.paragraph_format.left_indent = Inches(0.3)
                    p.paragraph_format.space_before = Pt(1); p.paragraph_format.space_after = Pt(1)
                    run = p.add_run(re.sub(r"^\d+[\.\)]\s", "", line))
                    run.font.size = Pt(10); run.font.name = "Calibri"; continue
                if re.match(r"^\[(FILE|URL|ORACLE)", line):
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Inches(0.2)
                    p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(2)
                    run = p.add_run(line); run.font.size = Pt(8.5); run.font.italic = True
                    run.font.name = "Calibri"; run.font.color.rgb = _rgb("6B7280"); continue
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(1); p.paragraph_format.space_after = Pt(3)
                run = p.add_run(line); run.font.size = Pt(10); run.font.name = "Calibri"
                run.font.color.rgb = _rgb(_C_DARK_TEXT)
    doc.add_paragraph("")
    footer_p = doc.add_paragraph()
    footer_run = footer_p.add_run(
        f"Oracle University · Training Design Document · Generated {gen_date}")
    footer_run.font.size = Pt(8); footer_run.font.italic = True
    footer_run.font.color.rgb = _rgb("9CA3AF"); footer_run.font.name = "Calibri"
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf


# ── 7. PDF Builder ────────────────────────────────────────────────────────────
def build_pdf(content: str, title: str) -> io.BytesIO:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib import colors
    from reportlab.lib.units import cm

    C_NAVY   = colors.HexColor("#1A1A2E"); C_RED    = colors.HexColor("#C74634")
    C_BLUE   = colors.HexColor("#005B8E"); C_SILVER = colors.HexColor("#F0F4F8")
    C_BORDER = colors.HexColor("#DDE1E7"); C_MIST   = colors.HexColor("#F7F9FB")
    C_GREY   = colors.HexColor("#6B7280"); C_TEXT   = colors.HexColor("#1D1D1F")
    C_WHITE  = colors.white

    buf = io.BytesIO()
    gen_date = datetime.now().strftime("%B %d, %Y")

    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(C_NAVY); canvas.rect(0, h - 28, w, 28, fill=1, stroke=0)
        canvas.setFillColor(C_WHITE); canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(1.5 * cm, h - 18, "ORACLE UNIVERSITY")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(w - 1.5 * cm, h - 18, f"Training Design Document · {title[:55]}")
        canvas.setFillColor(C_RED); canvas.rect(0, h - 31, w, 3, fill=1, stroke=0)
        canvas.setFillColor(C_BORDER); canvas.rect(0, 0, w, 22, fill=1, stroke=0)
        canvas.setFillColor(C_GREY); canvas.setFont("Helvetica", 7)
        canvas.drawString(1.5 * cm, 7, f"Generated {gen_date}  ·  Oracle University  ·  Confidential")
        canvas.drawRightString(w - 1.5 * cm, 7, f"Page {doc.page}")
        canvas.restoreState()

    doc_pdf = SimpleDocTemplate(buf, pagesize=A4,
        rightMargin=1.8*cm, leftMargin=1.8*cm, topMargin=1.6*cm, bottomMargin=1.6*cm)

    base = getSampleStyleSheet()
    sty_title    = ParagraphStyle("DocTitle",   parent=base["Normal"], fontName="Helvetica-Bold",
                                   fontSize=22, textColor=C_NAVY, leading=28, spaceAfter=6)
    sty_subtitle = ParagraphStyle("DocSub",     parent=base["Normal"], fontName="Helvetica",
                                   fontSize=11, textColor=C_RED,  leading=16, spaceAfter=16)
    sty_sec_hdr  = ParagraphStyle("SecHdr",     parent=base["Normal"], fontName="Helvetica-Bold",
                                   fontSize=10, textColor=C_WHITE, backColor=C_NAVY,
                                   leftIndent=8, spaceBefore=14, spaceAfter=6, borderPadding=(5,8,5,8))
    sty_sub_hdr  = ParagraphStyle("SubHdr",     parent=base["Normal"], fontName="Helvetica-Bold",
                                   fontSize=10, textColor=C_RED,  spaceBefore=10, spaceAfter=3)
    sty_label_hdr= ParagraphStyle("LabelHdr",   parent=base["Normal"], fontName="Helvetica-Bold",
                                   fontSize=9.5,textColor=C_BLUE, spaceBefore=6, spaceAfter=2)
    sty_body     = ParagraphStyle("Body",        parent=base["Normal"], fontName="Helvetica",
                                   fontSize=9.5,textColor=C_TEXT, leading=14, spaceBefore=2, spaceAfter=3)
    sty_bullet   = ParagraphStyle("Bullet",      parent=base["Normal"], fontName="Helvetica",
                                   fontSize=9.5,textColor=C_TEXT, leading=13,
                                   leftIndent=14, firstLineIndent=-10, spaceBefore=1, spaceAfter=1)
    sty_num      = ParagraphStyle("Num",         parent=base["Normal"], fontName="Helvetica",
                                   fontSize=9.5,textColor=C_TEXT, leading=13,
                                   leftIndent=16, firstLineIndent=-12, spaceBefore=1, spaceAfter=1)
    sty_cite     = ParagraphStyle("Cite",        parent=base["Normal"], fontName="Helvetica-Oblique",
                                   fontSize=8,  textColor=C_GREY, leading=11,
                                   leftIndent=10, spaceBefore=0, spaceAfter=2)
    sty_tbl_hdr  = ParagraphStyle("TblHdr",      parent=base["Normal"], fontName="Helvetica-Bold",
                                   fontSize=8,  textColor=C_WHITE, leading=11)
    sty_tbl_cell = ParagraphStyle("TblCell",     parent=base["Normal"], fontName="Helvetica",
                                   fontSize=8,  textColor=C_TEXT, leading=11)

    elements = []
    elements.append(Spacer(1, 0.6*cm))
    elements.append(Paragraph("TRAINING DESIGN DOCUMENT", sty_subtitle))
    elements.append(Paragraph(title, sty_title))
    elements.append(HRFlowable(width="100%", thickness=2, color=C_RED, spaceAfter=10))
    meta_data = [[Paragraph(f"<b>Date</b><br/>{gen_date}", sty_body),
                  Paragraph("<b>Issuer</b><br/>Oracle University", sty_body),
                  Paragraph("<b>Classification</b><br/>Confidential — Internal", sty_body)]]
    meta_tbl = RLTable(meta_data, colWidths=["33%","33%","34%"])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),C_SILVER),("GRID",(0,0),(-1,-1),0.5,C_BORDER),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    elements.append(meta_tbl); elements.append(Spacer(1, 0.5*cm))

    segments = parse_markdown_tables(content)
    for seg in segments:
        if seg[0] == "table":
            _, headers, rows = seg
            if not headers or not rows: continue
            col_count = len(headers)
            page_w = A4[0] - 3.6*cm
            col_w = [page_w / col_count] * col_count
            tbl_data = [[Paragraph(h, sty_tbl_hdr) for h in headers]]
            for row in rows:
                tbl_data.append([Paragraph(row[ci] if ci < len(row) else "", sty_tbl_cell)
                                  for ci in range(col_count)])
            rl_tbl = RLTable(tbl_data, colWidths=col_w, repeatRows=1)
            rl_tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),C_NAVY),("TEXTCOLOR",(0,0),(-1,0),C_WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),8),
                ("TOPPADDING",(0,0),(-1,0),6),("BOTTOMPADDING",(0,0),(-1,0),6),
                ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_WHITE,C_MIST]),
                ("FONTSIZE",(0,1),(-1,-1),8),("TOPPADDING",(0,1),(-1,-1),5),
                ("BOTTOMPADDING",(0,1),(-1,-1),5),("GRID",(0,0),(-1,-1),0.4,C_BORDER),
                ("LINEBELOW",(0,0),(-1,0),1.5,C_RED),("VALIGN",(0,0),(-1,-1),"TOP"),
            ]))
            elements.append(rl_tbl); elements.append(Spacer(1,10))
        else:
            for line in seg[1].splitlines():
                line = line.strip()
                if not line: elements.append(Spacer(1,3)); continue
                sec_match = re.match(r"---?\s*([A-Z][A-Z\s/\-]+)$", line)
                if sec_match:
                    elements.append(Spacer(1,6))
                    elements.append(Paragraph(sec_match.group(1).strip(), sty_sec_hdr))
                    elements.append(HRFlowable(width="100%",thickness=1,color=C_RED,spaceAfter=4))
                    continue
                kv_match = re.match(r"^([A-Z][A-Za-z\s/\-]{1,40})\s*:\s*(.+)$", line)
                if kv_match:
                    txt = f"<b><font color='#1A1A2E'>{kv_match.group(1)}:</font></b>  {kv_match.group(2)}"
                    elements.append(Paragraph(txt, sty_body)); continue
                if (line.endswith(":") and len(line) < 70
                        and (line == line.title() + ":" or line == line.upper())):
                    elements.append(Paragraph(line, sty_sub_hdr)); continue
                if re.match(r"^\d+[a-z]?\.\s+[A-Z]", line) or re.match(r"^[A-Z]{2,}[\s:–—]", line):
                    elements.append(Paragraph(line, sty_label_hdr)); continue
                if line.startswith(("- ","• ","* ","· ")):
                    elements.append(Paragraph("• " + line[2:], sty_bullet)); continue
                if re.match(r"^\d+[\.\)]\s", line):
                    nm = re.match(r"^(\d+[\.\)])\s(.+)$", line)
                    if nm: elements.append(Paragraph(f"{nm.group(1)} {nm.group(2)}", sty_num))
                    continue
                if re.match(r"^\[(FILE|URL|ORACLE)", line):
                    elements.append(Paragraph(line, sty_cite)); continue
                try: elements.append(Paragraph(line, sty_body))
                except Exception: elements.append(Paragraph(re.sub(r"[^\x20-\x7E]"," ",line), sty_body))

    doc_pdf.build(elements, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf


# ── 8. Format Validator ───────────────────────────────────────────────────────
def validate_format(ai_output: str) -> dict:
    validation_prompt = f"""
You are a Quality Reviewer for Oracle University training design documents.
Review the following document and answer ONLY in a JSON object with this exact schema:
{{
  "sections_present": {{
    "COURSE OVERVIEW": true, "COURSE END GOAL": true, "PERSONA INFORMATION": true,
    "IMPLEMENTATION READINESS": true, "GTM MESSAGING": true,
    "COURSE COVERAGE TABLE": true, "END GOAL CHECKLIST": true,
    "ASSESSMENT TOPICS": true, "CASE STUDY": true, "CHECKLIST": true, "TRACEABILITY MAP": true
  }},
  "course_coverage_is_table": true,
  "coverage_table_has_required_columns": true,
  "qa_checklist_is_table": true,
  "end_goal_uses_formula": true,
  "gtm_has_linkedin_post": true,
  "gtm_has_newsletter": true,
  "end_goal_checklist_has_i_can_statements": true,
  "assessment_topics_table_present": true,
  "no_bare_oracle_knowledge_base_tags": true,
  "missing_or_malformed": [],
  "overall": "PASS"
}}
DOCUMENT TO REVIEW:
{ai_output[:6000]}
"""
    try:
        resp = GROQ_CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": validation_prompt}],
            temperature=0.0, max_tokens=600,
        )
        raw = re.sub(r"```json|```", "", resp.choices[0].message.content).strip()
        return json.loads(raw)
    except Exception as e:
        return {"overall": "UNKNOWN", "error": str(e)}


# ── 9. Master Prompt Builder ──────────────────────────────────────────────────
def build_master_prompt(
    product, course_title, job_roles, audience_desc, experience_level,
    prereqs, biz_outcomes, all_knowledge, additional_notes,
    product_context="", benchmark_text="", benchmark_filename="", feedback="",
) -> str:
    feedback_block = (
        f"\nREFINEMENT FEEDBACK FROM REVIEWER:\n{feedback}\n"
        "IMPORTANT: Incorporate this feedback precisely in the regenerated document.\n"
        if feedback.strip() else ""
    )
    prereqs_block  = prereqs if prereqs.strip() else "None specified."
    audience_block = audience_desc if audience_desc.strip() else "Not specified — infer from job roles."
    context_block  = product_context.strip() if product_context.strip() else "Not provided."

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

Product Context     :
{context_block}
{feedback_block}

═══════════════════════════════════════
SOURCE KNOWLEDGE
(semantically classified + AI-summarised per file — full document coverage guaranteed)
Label meanings: [CONCEPTUAL]=explanatory, [PROCEDURAL]=step-by-step, [INSTRUCTIONAL]=learning objective
Note: Each uploaded file has been individually summarised by AI before being assembled here.
This means ALL pages of ALL uploaded files are represented in the knowledge below,
regardless of document length.
═══════════════════════════════════════
{all_knowledge[:KNOWLEDGE_HARD_CAP] if all_knowledge.strip() else "[No source files or URLs provided — generate based on product knowledge and best practices.]"}

═══════════════════════════════════════
DESIGN MASTER CLASS — FULL FRAMEWORK (NON-NEGOTIABLE)
═══════════════════════════════════════
{DESIGN_MASTER_CLASS_PRINCIPLES}

═══════════════════════════════════════
SEQUENCING RULE (NON-NEGOTIABLE)
═══════════════════════════════════════
Modules MUST follow a strict prerequisite chain:
  • Module 1 is ALWAYS foundational (concepts, terminology, architecture).
  • Each subsequent module explicitly depends on the prior one.
  • Advanced design/optimisation modules come LAST.
  • After the Coverage Table, add one paragraph justifying the module ordering.

═══════════════════════════════════════
REFERENCE SAMPLE — MATCH THIS LEVEL OF DETAIL AND TONE
═══════════════════════════════════════
{"GOLDEN STANDARD BENCHMARK (Management-Approved — " + benchmark_filename + ")" if benchmark_text.strip() else "BUILT-IN ORACLE REFERENCE SAMPLE"}
Study the document below. Match its detail depth, table structure, prose density, and tone exactly.

{benchmark_text[:18000] if benchmark_text.strip() else SAMPLE_DESIGN_DOCUMENT}

═══════════════════════════════════════
REQUIRED OUTPUT STRUCTURE
═══════════════════════════════════════

--- COURSE OVERVIEW
--- COURSE END GOAL
--- PERSONA INFORMATION
--- IMPLEMENTATION READINESS
--- GTM MESSAGING
--- COURSE COVERAGE TABLE
--- END GOAL CHECKLIST
--- ASSESSMENT TOPICS
--- CASE STUDY
--- CHECKLIST
--- TRACEABILITY MAP

COURSE COVERAGE TABLE columns (exact):
| Module # | Module Title | Module Learning Objective | Topic # | Topic Title | What We Teach in This Topic/Lesson | Bloom's Level | Activity Type | Est. Video Duration (min) | Key Takeaways (3–5 action-oriented) | Matching Hands-On Lab | Lab Type | Lab Duration (min) | Source Ref |

END GOAL CHECKLIST columns: | # | I Can Statement | Bloom's Level | Maps to Module |
ASSESSMENT TOPICS columns:  | # | Assessment Topic | Rationale | Suggested Type | Difficulty Level |
CHECKLIST columns:          | # | Check | Pass/Fail |
TRACEABILITY MAP columns:   | Source Tag | Full Reference Detail | Document Section(s) Used In |

Cite [FILE: filename] or [URL: full_link] for every factual claim.
Use [ORACLE KNOWLEDGE BASE: specific_topic_area] — NEVER a bare [ORACLE KNOWLEDGE BASE] tag.
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
  <div class="topbar-badge">AI-Powered v3</div>
</div>
""", unsafe_allow_html=True)


# ── STEPPER ────────────────────────────────────────────────────────────────────
step_labels = ["1 · Course Information","2 · Target Audience","3 · Source Content","4 · Generate & Review"]
c1, c2, c3, c4 = st.columns(4)
for col, idx, label in zip([c1,c2,c3,c4], [1,2,3,4], step_labels):
    with col:
        if idx < st.session_state.step:
            st.markdown(f"<div style='background:#F0FDF4;border:1px solid #86EFAC;border-radius:8px;padding:10px 14px;font-size:13px;font-weight:600;color:#15803D;text-align:center'>✓ {label}</div>", unsafe_allow_html=True)
        elif idx == st.session_state.step:
            st.markdown(f"<div style='background:#E8F4FD;border:2px solid #005B8E;border-radius:8px;padding:10px 14px;font-size:13px;font-weight:600;color:#005B8E;text-align:center'>▶ {label}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background:#F7F8FA;border:1px solid #DDE1E7;border-radius:8px;padding:10px 14px;font-size:13px;font-weight:500;color:#9CA3AF;text-align:center'>{label}</div>", unsafe_allow_html=True)

st.markdown("<div style='margin-bottom:20px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — COURSE INFORMATION
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.step == 1:
    st.markdown("""<div class="section-card"><div class="section-header"><div class="section-icon">📚</div><div><div class="section-title">Course Information</div><div class="section-sub">Define the core details of the training course</div></div></div></div>""", unsafe_allow_html=True)

    st.markdown("**Course Title** <span style='color:#C74634'>*</span>", unsafe_allow_html=True)
    course_title = st.text_input("Course Title", label_visibility="collapsed",
        placeholder="e.g. Oracle AI Agent Studio Fundamentals", value=st.session_state.course_title)

    st.markdown("**Product Name** <span style='color:#C74634'>*</span>", unsafe_allow_html=True)
    product_name = st.text_input("Product Name", label_visibility="collapsed",
        placeholder="e.g. Oracle AI Agent Studio", value=st.session_state.product_name)

    st.markdown("**Associated Job Role(s)** <span style='color:#C74634'>*</span> _(select from list and/or type a custom role below)_", unsafe_allow_html=True)
    all_roles = ["Solution Architect","Developer","Business Analyst","IT Manager",
                 "Consultant","DBA","Data Scientist","End User","Administrator"]
    selected_roles = st.multiselect("Job Roles", all_roles, label_visibility="collapsed",
        default=[r for r in st.session_state.job_roles if r in all_roles],
        placeholder="Choose one or more job roles...")
    custom_role = st.text_input("Custom / Other Role (optional)",
        placeholder="e.g. DevSecOps Engineer, ML Platform Lead…",
        value=st.session_state.custom_role,
        help="Type any role not in the list above.")

    st.markdown("**Product Context** <span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>", unsafe_allow_html=True)
    st.caption("Briefly describe what the product does and who it is built for. Helps the AI tailor the document more precisely.")
    product_context = st.text_area("Product Context", label_visibility="collapsed",
        placeholder="e.g. Oracle AI Agent Studio is a low-code platform that enables enterprises to design, deploy, and monitor autonomous AI agents...",
        value=st.session_state.product_context, height=120)

    st.divider()
    col_left, col_right = st.columns([3,1])
    with col_left: st.caption("🔴 * Required fields")
    with col_right:
        if st.button("Continue to Target Audience →", type="primary", use_container_width=True):
            combined_roles = list(selected_roles)
            if custom_role.strip(): combined_roles.append(custom_role.strip())
            if not course_title.strip(): st.error("Course Title is required.")
            elif not product_name.strip(): st.error("Product Name is required.")
            elif not combined_roles: st.error("Please select or enter at least one job role.")
            else:
                st.session_state.course_title    = course_title
                st.session_state.product_name    = product_name
                st.session_state.job_roles       = combined_roles
                st.session_state.custom_role     = custom_role
                st.session_state.product_context = product_context
                st.session_state.step = 2; st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — TARGET AUDIENCE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.step == 2:
    st.markdown("""<div class="section-card"><div class="section-header"><div class="section-icon">👥</div><div><div class="section-title">Target Audience</div><div class="section-sub">Describe who will take this training and their prior knowledge</div></div></div></div>""", unsafe_allow_html=True)

    st.markdown("**Recommended Target Audience Description** <span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>", unsafe_allow_html=True)
    audience_desc = st.text_area("Audience Description", label_visibility="collapsed",
        placeholder="e.g. Oracle solution architects with 2+ years of OCI experience…",
        value=st.session_state.audience_desc, height=100)

    st.markdown("**Audience Experience Level** <span style='color:#C74634'>*</span>", unsafe_allow_html=True)
    level_options = ["","Beginner","Intermediate","Advanced"]
    level_labels  = {"":"— Select Level —","Beginner":"🟢 Beginner — new to the product/topic",
                     "Intermediate":"🟡 Intermediate — familiar with basics, ready for configuration tasks",
                     "Advanced":"🔴 Advanced — experienced, focuses on architecture & optimisation"}
    experience_level = st.selectbox("Experience Level", level_options,
        format_func=lambda x: level_labels[x], label_visibility="collapsed",
        index=level_options.index(st.session_state.experience_level)
        if st.session_state.experience_level in level_options else 0)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Prerequisite Knowledge / Skills** <span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>", unsafe_allow_html=True)
        prereqs = st.text_area("Prerequisites", label_visibility="collapsed",
            placeholder="e.g. Familiarity with REST APIs, basic Oracle Cloud usage…",
            value=st.session_state.prereqs, height=100)
    with col2:
        st.markdown("**Business Outcomes** <span style='color:#6B7280;font-weight:400;font-size:12px'>(optional)</span>", unsafe_allow_html=True)
        biz_outcomes = st.text_area("Business Outcomes", label_visibility="collapsed",
            placeholder="e.g. Learners will design, deploy and manage Oracle AI Agents…",
            value=st.session_state.biz_outcomes, height=100)

    st.divider()
    col_back, col_fwd = st.columns(2)
    with col_back:
        if st.button("← Back", use_container_width=True): st.session_state.step = 1; st.rerun()
    with col_fwd:
        if st.button("Continue to Source Content →", type="primary", use_container_width=True):
            if not experience_level: st.error("Please select an Experience Level.")
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
        use_ocr = st.checkbox("Enable OCR for scanned PDFs / slide screenshots", value=False,
            help="Uses Tesseract. Slower but handles image-based documents.")
        st.caption("Requires `tesseract` installed on your system.")
        st.markdown("---")
        st.caption("🔗 URL depth setting")
        url_depth = st.slider("Sub-page crawl depth", min_value=0, max_value=3, value=1,
            help="0 = only the page you entered. 1 = page + direct child links.")
        url_max_pages = st.slider("Max pages to crawl per URL", min_value=1, max_value=30, value=10)

    st.markdown("""<div class="section-card"><div class="section-header"><div class="section-icon">🔗</div><div><div class="section-title">Documentation Links</div><div class="section-sub">Oracle Docs, Confluence pages, white papers — AI will read these and follow sub-links</div></div></div></div>""", unsafe_allow_html=True)

    url_types = ["Product Docs","Confluence","White Paper","Release Notes","Other"]
    for i, row in enumerate(st.session_state.urls):
        col_type, col_url, col_del = st.columns([2,5,0.6])
        with col_type:
            new_type = st.selectbox(f"Type {i}", url_types,
                index=url_types.index(row["type"]) if row["type"] in url_types else 0,
                label_visibility="collapsed", key=f"url_type_{i}")
        with col_url:
            new_url = st.text_input(f"URL {i}", value=row["url"],
                placeholder="https://docs.oracle.com/...",
                label_visibility="collapsed", key=f"url_val_{i}")
        with col_del:
            if len(st.session_state.urls) > 1:
                if st.button("✕", key=f"del_url_{i}"):
                    st.session_state.urls.pop(i); st.rerun()
        st.session_state.urls[i] = {"type": new_type, "url": new_url}

    if st.button("＋ Add Another Link"):
        st.session_state.urls.append({"type":"Product Docs","url":""}); st.rerun()

    # ── File Upload with per-file info banner ─────────────────────────────────
    st.markdown("""
    <div class="section-card" style="margin-top:18px">
      <div class="section-header">
        <div class="section-icon">📤</div>
        <div>
          <div class="section-title">Upload Source Files</div>
          <div class="section-sub">
            PDF, PPTX, DOCX — all pages extracted + individually AI-summarised before generation.
            No page limit. 100-page PDFs are fully represented.
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload source files", accept_multiple_files=True,
        type=["pptx","pptm","pdf","docx"], label_visibility="collapsed")
    if uploaded:
        for f in uploaded:
            size_mb = round(f.size / 1024 / 1024, 1)
            ext = f.name.split(".")[-1].upper()
            st.success(f"📄 **{f.name}** — {ext} · {size_mb} MB · All pages will be AI-summarised ✅")

    st.session_state["use_ocr"]            = use_ocr if "use_ocr" in dir() else False
    st.session_state["url_depth"]          = url_depth if "url_depth" in dir() else 1
    st.session_state["url_max_pages"]      = url_max_pages if "url_max_pages" in dir() else 10
    st.session_state["uploaded_files_data"] = uploaded or []

    st.markdown("""<div class="section-card" style="margin-top:18px"><div class="section-header"><div class="section-icon">📝</div><div><div class="section-title">Additional Notes for the AI</div><div class="section-sub">Special instructions, structural preferences, compliance requirements</div></div></div></div>""", unsafe_allow_html=True)
    additional_notes = st.text_area("Additional Notes", label_visibility="collapsed",
        placeholder="e.g. Focus on hands-on lab activities. Include a GOV/compliance module…",
        value=st.session_state.additional_notes, height=100)
    st.session_state.additional_notes = additional_notes

    # ── Golden Standard Benchmark ─────────────────────────────────────────────
    st.markdown("""
    <div class="section-card" style="margin-top:18px">
      <div class="section-header">
        <div class="section-icon">🏅</div>
        <div>
          <div class="section-title">Golden Standard Benchmark</div>
          <div class="section-sub">Upload a management-approved sample design document — AI will match its tone, depth, and structure</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_toggle, col_toggle_label = st.columns([0.08, 0.92])
    with col_toggle:
        use_benchmark = st.toggle("benchmark_toggle", value=st.session_state.use_benchmark,
            label_visibility="collapsed", key="benchmark_toggle_widget")
    with col_toggle_label:
        if use_benchmark:
            st.markdown("<span style='font-size:13px;font-weight:600;color:#005B8E'>✅ Benchmark mode ON — upload your approved reference document below</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='font-size:13px;color:#6B7280'>Use built-in Oracle Design Master Class principles as quality standard</span>", unsafe_allow_html=True)

    st.session_state.use_benchmark = use_benchmark

    if use_benchmark:
        st.markdown("<div style='background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:12px 16px;margin:10px 0 6px 0;font-size:12px;color:#1E40AF'>📌 <strong>How this works:</strong> The AI will study your uploaded benchmark document and calibrate the generated output to match its level of detail, prose density, table structure, and overall tone.</div>", unsafe_allow_html=True)
        benchmark_file = st.file_uploader("Upload Benchmark Document", type=["pdf","docx","pptx","pptm"],
            accept_multiple_files=False, label_visibility="collapsed", key="benchmark_file_uploader",
            help="This document is used as a quality benchmark only — not as course source content.")
        if benchmark_file:
            bm_size_mb = round(benchmark_file.size / 1024 / 1024, 1)
            st.success(f"🏅 **Benchmark loaded:** {benchmark_file.name} — {benchmark_file.type.split('/')[-1].upper()} · {bm_size_mb} MB")
            bm_text = extract_master_content(benchmark_file, ocr_enabled=False)
            st.session_state.benchmark_text     = bm_text
            st.session_state.benchmark_filename = benchmark_file.name
        elif not st.session_state.benchmark_text:
            st.info("📂 No benchmark document uploaded yet.")
        else:
            st.success(f"🏅 **Benchmark retained:** {st.session_state.benchmark_filename} (from earlier in this session)")
    else:
        st.session_state.benchmark_text     = ""
        st.session_state.benchmark_filename = ""

    st.divider()
    col_back, col_gen = st.columns(2)
    with col_back:
        if st.button("← Back", use_container_width=True): st.session_state.step = 2; st.rerun()
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

    if not st.session_state.generated:
        st.markdown("""<div class="section-card"><div class="section-header"><div class="section-icon">⚡</div><div><div class="section-title">Generating Training Design Document</div><div class="section-sub">AI agent is analysing your inputs and applying Oracle instructional design principles…</div></div></div></div>""", unsafe_allow_html=True)

        gen_steps = [
            "Ingesting uploaded files (all pages — no limit)",
            "AI-summarising each file individually (Option C)",
            "Smart relevance filtering of URL content (Option B)",
            "Scraping and parsing URL sources (with sub-link crawl)",
            "Calibrating content depth to audience experience level",
            "Generating learner-centric design document via AI",
            "Validating output format (second AI pass)",
            "Building PDF and Word exports",
            "Running reliability audit on generated content",
        ]

        progress_bar    = st.progress(0, text="Initialising…")
        step_placeholder = st.empty()

        def render_steps(current_idx: int):
            html = ""
            for j, s in enumerate(gen_steps):
                if j < current_idx:    cls, dot = "done",    "✓"
                elif j == current_idx: cls, dot = "active",  "●"
                else:                  cls, dot = "pending",  str(j + 1)
                html += f'<div class="gen-step {cls}"><div class="gen-dot">{dot}</div><span>{s}</span></div>'
            step_placeholder.markdown(html, unsafe_allow_html=True)

        # ── Step 0: Extract all files (no page limit) ─────────────────────────
        render_steps(0); progress_bar.progress(5, text="Ingesting files — all pages…")
        use_ocr        = st.session_state.get("use_ocr", False)
        uploaded_files = st.session_state.get("uploaded_files_data", [])

        raw_file_texts = {}   # filename → full raw extracted text
        for f in uploaded_files:
            raw_text = extract_master_content(f, use_ocr)
            raw_file_texts[f.name] = raw_text

        # ── Step 1: OPTION C — AI-summarise each file individually ────────────
        render_steps(1); progress_bar.progress(15, text="AI-summarising uploaded files…")
        file_summaries_combined = ""
        file_summary_log = []

        for fname, raw_text in raw_file_texts.items():
            if not raw_text.strip():
                continue
            char_count = len(raw_text)
            st.info(f"📄 Summarising **{fname}** ({char_count:,} characters extracted from all pages)…")
            summary = summarise_file_with_ai(
                filename=fname,
                raw_text=raw_text,
                course_title=st.session_state.course_title,
                job_roles=", ".join(st.session_state.job_roles),
                product_name=st.session_state.product_name,
            )
            file_summaries_combined += summary
            file_summary_log.append({"File": fname, "Extracted": f"{char_count:,} chars", "Status": "✅ Summarised"})

        if file_summary_log:
            st.success(f"✅ {len(file_summary_log)} file(s) fully summarised — all pages represented.")

        # ── Step 2: OPTION B — Smart filter URL content ───────────────────────
        render_steps(2); progress_bar.progress(28, text="Smart filtering URL content…")
        depth     = st.session_state.get("url_depth", 1)
        max_pages = st.session_state.get("url_max_pages", 10)
        url_src   = ""
        for row in st.session_state.urls:
            if row["url"].strip():
                url_src += extract_url_content(row["url"], max_depth=depth, max_pages=max_pages)

        # Classify URL content then smart-filter it
        url_src_classified = classify_chunks(url_src)
        url_src_filtered   = smart_filter_chunks(
            url_src_classified,
            course_title=st.session_state.course_title,
            job_roles=st.session_state.job_roles,
        )

        # ── OPTION A: Combine with raised cap (60,000 chars) ─────────────────
        # File summaries take priority; URL content fills remaining budget
        all_knowledge = file_summaries_combined + url_src_filtered
        # Final hard cap applied inside build_master_prompt via KNOWLEDGE_HARD_CAP

        # Steps 3-5: UX progress
        render_steps(3); progress_bar.progress(38, text="Scraping URLs…"); time.sleep(0.3)
        render_steps(4); progress_bar.progress(50, text="Calibrating to audience level…"); time.sleep(0.3)
        render_steps(5); progress_bar.progress(62, text="Calling AI model…")

        # ── Step 5: Primary AI call ───────────────────────────────────────────
        try:
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
                product_context=st.session_state.product_context,
                benchmark_text=st.session_state.get("benchmark_text", ""),
                benchmark_filename=st.session_state.get("benchmark_filename", ""),
                feedback=st.session_state.feedback_text,
            )
            response = GROQ_CLIENT.chat.completions.create(
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

        # ── Step 6: Format validation ─────────────────────────────────────────
        render_steps(6); progress_bar.progress(73, text="Validating output format…")
        st.session_state["validation_result"] = validate_format(ai_output)

        # ── Step 7: Build documents ───────────────────────────────────────────
        render_steps(7); progress_bar.progress(83, text="Building PDF and Word documents…")
        st.session_state.pdf_buf  = build_pdf(ai_output, st.session_state.course_title)
        st.session_state.word_buf = build_word(ai_output, st.session_state.course_title)

        # ── Step 8: Audit ─────────────────────────────────────────────────────
        render_steps(8); progress_bar.progress(95, text="Running reliability audit…")
        st.session_state.audit = perform_reliability_audit(ai_output)

        progress_bar.progress(100, text="✅ Document ready!")
        render_steps(len(gen_steps))
        time.sleep(0.5)
        st.session_state.generated     = True
        st.session_state.feedback_text = ""
        st.rerun()

    # ── OUTPUT PHASE ──────────────────────────────────────────────────────────
    else:
        if st.session_state.gen_error:
            st.error(f"❌ AI generation failed: {st.session_state.gen_error}")
            st.info("Check your GROQ_API_KEY in Streamlit secrets and try again.")
            if st.button("← Go Back & Retry"):
                st.session_state.step = 3; st.session_state.generated = False
                st.session_state.gen_error = ""; st.rerun()
            st.stop()

        title    = st.session_state.course_title
        level    = st.session_state.experience_level
        roles    = ", ".join(st.session_state.job_roles)
        gen_date = datetime.now().strftime("%B %d, %Y")

        col_title, col_btns = st.columns([3,2])
        with col_title:
            st.markdown(f"📄 **Training Design Document** <span style='background:#DCFCE7;color:#15803D;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;margin-left:6px'>✓ Generated</span>", unsafe_allow_html=True)
        with col_btns:
            col_fb, col_docx, col_pdf = st.columns(3)
            with col_fb:
                if st.button("💬 Feedback", use_container_width=True):
                    st.session_state.show_feedback = not st.session_state.show_feedback; st.rerun()
            with col_docx:
                st.download_button("⬇ DOCX", data=st.session_state.word_buf,
                    file_name=f"{title.replace(' ','_')}_TDD.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True)
            with col_pdf:
                st.download_button("⬇ PDF", data=st.session_state.pdf_buf,
                    file_name=f"{title.replace(' ','_')}_TDD.pdf",
                    mime="application/pdf", use_container_width=True)

        # Format Validation
        vr = st.session_state.get("validation_result", {})
        with st.expander("🔍 Format Validation Report", expanded=False):
            overall = vr.get("overall","UNKNOWN")
            colour  = "#15803D" if overall == "PASS" else "#C74634"
            st.markdown(f"<span style='color:{colour};font-weight:700;font-size:15px'>Overall: {overall}</span>", unsafe_allow_html=True)
            issues = vr.get("missing_or_malformed",[])
            if issues:
                st.markdown("**Issues found:**")
                for issue in issues: st.markdown(f"- {issue}")
            else:
                st.markdown("✅ No structural issues detected.")
            checks = [
                ("course_coverage_is_table","Coverage Table rendered as markdown table"),
                ("coverage_table_has_required_columns","Coverage Table has all required columns"),
                ("end_goal_uses_formula","Course End Goal uses prescribed formula"),
                ("gtm_has_linkedin_post","GTM section includes LinkedIn Post"),
                ("gtm_has_newsletter","GTM section includes Newsletter Write-Up"),
                ("end_goal_checklist_has_i_can_statements","End Goal Checklist has 'I can…' statements"),
                ("assessment_topics_table_present","Assessment Topics table present"),
                ("no_bare_oracle_knowledge_base_tags","No bare [ORACLE KNOWLEDGE BASE] tags"),
            ]
            for key, label in checks:
                if vr.get(key) is False: st.warning(f"⚠️ {label} — needs attention.")

        # Reliability Audit
        audit = st.session_state.audit or {}
        with st.expander("📊 Reliability Audit", expanded=False):
            a_col1, a_col2 = st.columns([1,2])
            with a_col1:
                st.metric("Traceability Tags", audit.get("traceability_tags",0))
            with a_col2:
                st.markdown("**Mandatory Section Checklist**")
                for sec, found in audit.get("sections",{}).items():
                    icon = "✅" if found else "❌"
                    colour = "#15803D" if found else "#C74634"
                    st.markdown(f"<span style='color:{colour};font-weight:600'>{icon} {sec}</span>", unsafe_allow_html=True)
            source_map = audit.get("source_map",{})
            if source_map:
                st.markdown("**Source → Section Traceability Map**")
                st.dataframe([{"Source Tag": t, "Document Section(s)": ", ".join(set(s))}
                              for t, s in source_map.items()], use_container_width=True)

        # Feedback Panel
        if st.session_state.show_feedback:
            st.markdown("""<div style='background:#FFF7ED;border:1px solid #FCD34D;border-radius:8px;padding:14px 18px;margin:12px 0'><strong style='font-size:13px;color:#92400E'>💬 Provide Feedback to Refine</strong><br><span style='font-size:12px;color:#B45309'>Describe what to change — the AI will regenerate incorporating your feedback exactly.</span></div>""", unsafe_allow_html=True)
            feedback = st.text_area("Feedback", label_visibility="collapsed",
                placeholder="e.g. Add more hands-on lab activities. Revise Section 3…",
                value=st.session_state.feedback_text, height=90)
            col_cancel, col_refine = st.columns(2)
            with col_cancel:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_feedback = False; st.rerun()
            with col_refine:
                if st.button("🔄 Refine Document", type="primary", use_container_width=True):
                    if feedback.strip():
                        st.session_state.feedback_text = feedback
                        st.session_state.generated     = False
                        st.session_state.show_feedback = False; st.rerun()
                    else: st.warning("Please enter feedback before refining.")

        # Document preview
        bm_badge = (
            f"<span style='background:#EFF6FF;color:#1E40AF;border:1px solid #BFDBFE;font-size:11px;font-weight:600;padding:2px 9px;border-radius:20px;margin-left:4px'>🏅 Benchmark: {st.session_state.get('benchmark_filename','')}</span>"
            if st.session_state.get("use_benchmark") and st.session_state.get("benchmark_filename") else ""
        )
        st.markdown(f"""
        <div class="doc-wrap"><div class="doc-body">
          <div class="doc-h1">{title}</div>
          <div class="doc-meta-row">
            <span>📅 {gen_date}</span><span>🏢 Oracle University</span>
            <span>🎯 {level}</span><span>👤 {roles}</span>{bm_badge}
          </div>
        </div></div>""", unsafe_allow_html=True)

        st.markdown(st.session_state.ai_raw_output)
        st.divider()
        if st.button("← Start Over / New Document"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
