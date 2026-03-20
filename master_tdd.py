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
- TRACEABILITY: Cite [FILE:...] or [URL:...] for every module.
- MAPPING: JTA tasks must link to Bloom objectives.
- 80/20: Prioritize core implementation skills.
"""

st.set_page_config(page_title="Universal Design Agent", page_icon="📘", layout="wide")

# --- Reliability Audit ---
def perform_reliability_audit(text):
    audit = {"sections": {}, "traceability_tags": 0, "passed": True}
    for sec in MANDATORY_SECTIONS:
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = True if found else False
        if not found: audit["passed"] = False
    tags = re.findall(r"\[(FILE|URL):.*?\]", text)
    audit["traceability_tags"] = len(tags)
    return audit

# --- Content Intelligence Layer ---
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

# --- NEW: URL Extraction Logic ---
def extract_url_content(url):
    if not url: return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator=' ')
        # Clean up whitespace
        clean_text = re.sub(r'\s+', ' ', text).strip()
        return f"\n[SOURCE URL: {url}]\n{clean_text[:15000]}\n"
    except Exception as e:
        return f"\nhttps://www.merriam-webster.com/dictionary/error: {e}\n"

# --- Multi-Source Extraction ---
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
                    text += f"\n[FILE: {file.name} | PAGE: {i+1}]\n{p_text}\n"
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

# --- UI Layout ---
st.sidebar.title("🛠️ Agent Controls")
use_ocr = st.sidebar.checkbox("Enable Vision/OCR", value=False)
custom_bench = st.sidebar.file_uploader("Upload Gold Standard", type=["pdf", "pptx", "docx"])

if "design_out" not in st.session_state: st.session_state.design_out = None
if "pdf_f" not in st.session_state: st.session_state.pdf_f = None
if "word_f" not in st.session_state: st.session_state.word_f = None

st.title("📘 Universal Design Agent")
c1, c2 = st.columns(2)
pn = c1.text_input("Product Pillar", value="Oracle Cloud EPM")
cn = c2.text_input("Course Title")

# --- NEW: Link Input Field ---
url_input = st.text_input("🔗 Paste Documentation URL (Oracle Help Center, Blogs, etc.)", placeholder="https://docs.oracle.com/...")

jt = st.text_area("Job Task Analysis (JTA)")
files = st.file_uploader("📂 Source Documentation (PDF, PPTX, DOCX)", type=["pdf", "pptx", "pptm", "docx"], accept_multiple_files=True)

# --- Builders ---
def build_pdf(content, cn):
    buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=landscape(A4)); styles = getSampleStyleSheet()
    elements = [Paragraph(f"TDD: {cn}", styles['Title']), Spacer(1, 12)]
    for line in content.split('\n'): elements.append(Paragraph(line, styles['Normal']))
    doc.build(elements); buf.seek(0); return buf

def build_word(content, cn):
    doc = DocxDocument(); doc.add_heading(f"TDD: {cn}", 0)
    for line in content.split('\n'): doc.add_paragraph(line)
    buf = io.BytesIO(); doc.save(buf); buf.seek(0); return buf

# --- Orchestrator ---
# --- Updated Orchestrator with Oracle-Spec Logic ---
if st.button("🚀 Generate Reliable Design", use_container_width=True):
    with st.status("🛠️ Analyzing Multi-Source Content...", expanded=True) as status:
        
        bench = extract_master_content(custom_bench, use_ocr) if custom_bench else GOLD_STANDARD_FALLBACK
        
        # This combines your PDF, PPT, and URL into one source!
        file_src = "".join([extract_master_content(f, use_ocr) for f in files])
        url_src = extract_url_content(url_input)
        all_src = file_src + url_src
        
        intel = classify_instructional_content(all_src)
        
        try:
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        except:
            st.error("🔑 API Key Missing!"); st.stop()

        # We are adding "Consultant-Grade" instructions here
        prompt = f"""
        ACT AS: Senior Oracle Instructional Designer. 
        AUDIENCE: Functional Consultants (Implementers).
        SOURCE DATA: {intel[:10000]}
        BENCHMARK: {bench[:2000]}
        INPUTS: {pn}, {cn}, {jt}

        STRICT INSTRUCTIONS:
        1. HEADERS: Use exact headers: {', '.join(['--- ' + s for s in MANDATORY_SECTIONS])}. (Check spelling: 'OVERVIEW', not 'OVERVERAGE').
        2. BLOOM'S: Configuration tasks must be 'Applying' or 'Analyzing'. Do not use 'Remembering' for technical setup.
        3. 80/20 RULE: Include a 'Troubleshooting' or 'Best Practices' topic in the Course Coverage Table.
        4. MEASURABILITY: Success criteria in the table must be specific (e.g., 'Successfully resolve 3 prediction errors' instead of 'Understand errors').
        5. TRACEABILITY: You MUST cite [FILE: Name] or [URL: Link] for every module.
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
    
    st.download_button("📄 Download PDF", data=st.session_state.pdf_f, file_name="TDD.pdf")
    st.download_button("📝 Download Word", data=st.session_state.word_f, file_name="TDD.docx")
    st.markdown("---")
    st.markdown(st.session_state.design_out)
