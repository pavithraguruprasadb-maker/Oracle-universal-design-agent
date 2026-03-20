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
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = True if found else False
        if not found: audit["passed"] = False
    tags = re.findall(r"\[FILE:.*?\]", text)
    audit["traceability_tags"] = len(tags)
    if len(tags) < 3: audit["passed"] = False
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
    ext = file.name.split('.')[-1].lower()
    try:
        if ext == "pdf":
            f_bytes = file.read()
            with pdfplumber.open(io.BytesIO(f_bytes)) as pdf:
                for i, page in enumerate(pdf.pages):
                    p_text = page.extract_text() or ""
                    tables = page.extract_tables()
                    t_text = ""
                    for table in tables:
                        for row in table: t_text += " | ".join([str(c) if c else "[SPANNED]" for c in row]) + "\n"
                    
                    ocr_text = ""
                    if ocr_enabled and (not p_text.strip() or len(p_text) < 200):
                        imgs = convert_from_bytes(f_bytes, first_page=i+1, last_page=i+1)
                        for img in imgs: ocr_text += f"\n[OCR]: {pytesseract.image_to_string(img)}\n"
                    text += f"\n[FILE: {file.name} | PAGE: {i+1}]\n{p_text}\n{t_text}\n{ocr_text}\n"
        elif ext in ["pptx", "pptm"]:
            prs = Presentation(file)
            for i, slide in enumerate(prs.slides):
                s_txt = ""
                for shape in slide.shapes:
                    if hasattr(shape, "text"): s_txt += shape.text + " "
                    if shape.has_table:
                        for row in shape.table.rows: s_txt += " | ".join([c.text_frame.text if not c.is_spanned else "[SPANNED]" for c in row.cells]) + "\n"
                text += f"\n[FILE: {file.name} | SLIDE: {i+1}]\n{s_txt}\n"
        elif ext == "docx":
            doc = DocxRead(file)
            for idx, p in enumerate(doc.paragraphs):
                if p.text.strip(): text += f"\n[FILE: {file.name} | PARA: {idx+1}]\n{p.text}\n"
    except Exception as e: st.error(f"Ingestion Failure: {e}")
    return text

# --- Sidebar Controls ---
st.sidebar.title("🛠️ Agent Controls")
use_ocr = st.sidebar.checkbox("Enable Vision/OCR", value=False)
custom_bench = st.sidebar.file_uploader("Upload Gold Standard (7.2)", type=["pdf", "pptx", "docx"])

if "design_out" not in st.session_state: st.session_state.design_out = None
if "pdf_f" not in st.session_state: st.session_state.pdf_f = None
if "word_f" not in st.session_state: st.session_state.word_f = None

# --- Main UI ---
st.title("📘 Universal Design Agent")
pn = st.text_input("Product Pillar", placeholder="e.g. Oracle Cloud EPM")
cn = st.text_input("Course Title")
jt = st.text_area("Job Task Analysis (JTA)", placeholder="List core tasks for mapping...")

st.markdown("---")
files = st.file_uploader("📂 Source Documentation", type=["pdf", "pptx", "pptm", "docx"], accept_multiple_files=True)

# --- Document Builders ---
def build_pdf(content, cn):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=16, textColor=colors.white, backColor=colors.HexColor('#1a237e'), borderPadding=8)
    elements = [Paragraph(f"TDD: {cn}", styles['Title']), Spacer(1, 10)]
    for line in content.split('\n'):
        if any(line.upper().startswith(s) for s in MANDATORY_SECTIONS): elements.append(Paragraph(line, h1))
        else: elements.append(Paragraph(line, styles['Normal']))
    doc.build(elements); buf.seek(0); return buf

def build_word(content, cn):
    doc = DocxDocument()
    doc.add_heading(f"Training Design Document: {cn}", 0)
    for line in content.split('\n'):
        if any(line.upper().startswith(s) for s in MANDATORY_SECTIONS): doc.add_heading(line, level=1)
        else: doc.add_paragraph(line)
    buf = io.BytesIO(); doc.save(buf); buf.seek(0); return buf

# --- Orchestrator ---
if files and st.button("🚀 Generate Reliable Design", use_container_width=True):
    with st.status("🛠️ Running Master Class Logic Engine...", expanded=True) as status:
        
        bench = extract_master_content(custom_bench, use_ocr) if custom_bench else GOLD_STANDARD_FALLBACK
        src = "".join([extract_master_content(f, use_ocr) for f in files])
        intel = classify_instructional_content(src)
        
        try:
            # SECURE KEY INTEGRATION
            api_key = st.secrets["GROQ_API_KEY"]
            client = Groq(api_key=api_key)
        except Exception:
            st.error("🔑 API Key Missing! Please add 'GROQ_API_KEY' to Streamlit Secrets.")
            st.stop()

       prompt = f"""
        SOURCE DATA: {intel[:10000]}
        BENCHMARK: {bench[:2000]}
        INPUTS: {pn}, {cn}, {jt}

        STRICT RULES:
        1. You MUST use these exact headers (starting with '--- '): 
           --- COURSE OVERVIEW, --- JOB TASK TO SKILL MAPPING, --- CASE STUDY, --- GTM MESSAGING.
        2. Reference [FILE:...] tags for every technical claim.
        3. Use Bloom's Taxonomy for the Skill Mapping table.
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
        for s, found in audit["sections"].items(): st.write(f"{'✅' if found else '❌'} {s}")
    
    c1, c2, c3 = st.columns([1,1,1])
    c1.download_button("📄 Download PDF", data=st.session_state.pdf_f, file_name=f"{pn}_TDD.pdf", use_container_width=True)
    c2.download_button("📝 Download Word", data=st.session_state.word_f, file_name=f"{pn}_TDD.docx", use_container_width=True)
    if c3.button("🔄 Reset Agent"): st.rerun()
    
    st.markdown("---")
    st.markdown(st.session_state.design_out)
