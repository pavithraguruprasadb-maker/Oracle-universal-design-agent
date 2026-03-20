import streamlit as st
import pdfplumber
from groq import Groq
import io
import re
import time
from pptx import Presentation
from docx import Document as DocxRead
import requests
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

# PDF & Word Generation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER
from docx import Document as DocxDocument

# --- Requirement 7.1: Mandatory Sections ---
MANDATORY_SECTIONS = [
    "COURSE OVERVIEW",
    "JOB TASK TO SKILL MAPPING",
    "IMPLEMENTATION READINESS",
    "GTM MESSAGING",
    "COURSE COVERAGE TABLE",
    "CASE STUDY",
    "QA CHECKLIST"
]

GOLD_STANDARD_FALLBACK = """
### MASTER CLASS BENCHMARK
- TRACEABILITY: Cite [FILE:...] for every module.
- MAPPING: JTA tasks must link to Bloom objectives.
- 80/20: Prioritize core implementation skills.
"""

st.set_page_config(page_title="Universal Design Agent", page_icon="📘", layout="wide")

# --- Reliability Audit (Requirement: Second-Pass Validation) ---
def perform_reliability_audit(text):
    audit = {"sections": {}, "traceability_tags": 0, "passed": True}
    for sec in MANDATORY_SECTIONS:
        # Looking for the "--- " prefix we are forcing the AI to use
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = True if found else False
        if not found: audit["passed"] = False
    tags = re.findall(r"\[FILE:.*?\]", text)
    audit["traceability_tags"] = len(tags)
    return audit

# --- Content Intelligence Layer (6.2) ---
def classify_instructional_content(raw_text):
    intel = {"concepts": [], "procedures": [], "workflows": []}
    chunks = raw_text.split('\n\n')
    patterns = {"proc": [r"step", r"how to", r"click", r"select"], "flow": [r"workflow", r"process"], "conc": [r"is a", r"overview"]}
    for chunk in chunks:
        c = chunk.lower()
        if any(re.search(p, c) for p in patterns["proc"]): intel["procedures"].append(chunk)
        elif any(re.search(p, c) for p in patterns["flow"]): intel["workflows"].append(chunk)
        elif any(re.search(p, c) for p in patterns["conc"]): intel["concepts"].append(chunk)
    return f"[[ CONCEPTS ]]\n{' '.join(intel['concepts'][:10])}\n\n[[ PROCEDURES ]]\n{' '.join(intel['procedures'][:15])}"

# --- Multi-Source Extraction with Vision (6.1) ---
def extract_master_content(file, ocr_enabled=False):
    text = ""
    if file is None: return ""
    ext = file.name.split('.')[-1].lower()
    try:
        if ext == "pdf":
            f_bytes = file.read()
            with pdfplumber.open(io.BytesIO(f_bytes)) as pdf:
                for i, page in enumerate(pdf.pages):
                    p_text = page.extract_text() or ""
                    t_text = ""
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table: t_text += " | ".join([str(c) if c else "" for c in row]) + "\n"
                    text += f"\n[FILE: {file.name} | PAGE: {i+1}]\n{p_text}\n{t_text}\n"
        elif ext in ["pptx", "pptm"]:
            prs = Presentation(file)
            for i, slide in enumerate(prs.slides):
                s_txt = "".join([shape.text + " " for shape in slide.shapes if hasattr(shape, "text")])
                text += f"\n[FILE: {file.name} | SLIDE: {i+1}]\n{s_txt}\n"
        elif ext == "docx":
            doc = DocxRead(file)
            text += "\n".join([p.text for p in doc.paragraphs])
    except Exception as e: st.error(f"Error reading {file.name}: {e}")
    return text

# --- Sidebar ---
st.sidebar.title("🛠️ Agent Controls")
use_ocr = st.sidebar.checkbox("Enable Vision/OCR", value=False)
custom_bench = st.sidebar.file_uploader("Upload Gold Standard", type=["pdf", "pptx", "docx"])

if "design_out" not in st.session_state: st.session_state.design_out = None
if "pdf_f" not in st.session_state: st.session_state.pdf_f = None
if "word_f" not in st.session_state: st.session_state.word_f = None

# --- Main UI ---
st.title("📘 Universal Design Agent")
pn = st.text_input("Product Pillar", value="Oracle Cloud EPM")
cn = st.text_input("Course Title")
jt = st.text_area("Job Task Analysis (JTA)")

files = st.file_uploader("📂 Source Documentation", type=["pdf", "pptx", "pptm", "docx"], accept_multiple_files=True)

# --- Document Builders ---
def build_pdf(content, cn):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"TDD: {cn}", styles['Title']), Spacer(1, 12)]
    for line in content.split('\n'):
        elements.append(Paragraph(line, styles['Normal']))
    doc.build(elements); buf.seek(0); return buf

def build_word(content, cn):
    doc = DocxDocument()
    doc.add_heading(f"TDD: {cn}", 0)
    for line in content.split('\n'):
        doc.add_paragraph(line)
    buf = io.BytesIO(); doc.save(buf); buf.seek(0); return buf

# --- Orchestrator ---
if files and st.button("🚀 Generate Reliable Design", use_container_width=True):
    with st.status("🛠️ Running Master Class Logic Engine...", expanded=True) as status:
        
        bench = extract_master_content(custom_bench, use_ocr) if custom_bench else GOLD_STANDARD_FALLBACK
        src = "".join([extract_master_content(f, use_ocr) for f in files])
        intel = classify_instructional_content(src)
        
        try:
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        except Exception:
            st.error("🔑 API Key Missing in Secrets!")
            st.stop()

        # The Prompt handles the "Strict Rules" for headers
        prompt = f"""
        SOURCE DATA: {intel[:10000]}
        BENCHMARK STYLE: {bench[:2000]}
        INPUTS: {pn}, {cn}, {jt}

        INSTRUCTIONS:
        1. Use exact headers starting with '--- ' (e.g., --- COURSE OVERVIEW).
        2. Create a detailed table for '--- JOB TASK TO SKILL MAPPING'.
        3. Reference [FILE: Name | Page: X] for all technical claims.
        4. Sections required: {', '.join(MANDATORY_SECTIONS)}.
        """
        
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
        
        st.session_state.design_out = res.choices[0].message.content
        st.session_state.pdf_f = build_pdf(st.session_state.design_out, cn)
        st.session_state.word_f = build_word(st.session_state.design_out, cn)
        status.update(label="✅ Generation Complete!", state="complete")

# --- Results ---
if st.session_state.design_out:
    audit = perform_reliability_audit(st.session_state.design_out)
    with st.expander("📊 Reliability & Mapping Audit", expanded=True):
        c1, c2 = st.columns(2)
        c1.metric("Traceability Tags", audit["traceability_tags"])
        c2.write("Section Compliance:")
        for s, found in audit["sections"].items():
            st.write(f"{'✅' if found else '❌'} {s}")
    
    st.download_button("📄 Download PDF", data=st.session_state.pdf_f, file_name="TDD.pdf")
    st.download_button("📝 Download Word", data=st.session_state.word_f, file_name="TDD.docx")
    st.markdown("---")
    st.markdown(st.session_state.design_out)
