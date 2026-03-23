import streamlit as st
import pdfplumber
from groq import Groq
import io
import re
import requests
from bs4 import BeautifulSoup
from pptx import Presentation
from docx import Document as DocxRead
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes

# --- Document Generation ---
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT
from docx import Document as DocxDocument

# --- Configuration: Sections for Audit & Formatting ---
MANDATORY_SECTIONS = [
    "COURSE OVERVIEW",
    "PERSONA INFORMATION",
    "IMPLEMENTATION READINESS",
    "GTM MESSAGING",
    "COURSE COVERAGE TABLE",
    "CASE STUDY",
    "QA CHECKLIST"
]

st.set_page_config(page_title="Oracle Universal Design Agent", page_icon="📘", layout="wide")

# --- Logic: Reliability Audit ---
def perform_reliability_audit(text):
    audit = {"sections": {}, "traceability_tags": 0}
    for sec in MANDATORY_SECTIONS:
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = True if found else False
    tags = re.findall(r"\[(FILE|URL):.*?\]", text)
    audit["traceability_tags"] = len(tags)
    return audit

# --- Logic: Multi-Source Extraction (Tables + OCR + Scraper) ---
def extract_url_content(url):
    if not url: return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for s in soup(["script", "style"]): s.decompose()
        text = re.sub(r'\s+', ' ', soup.get_text()).strip()
        return f"\n[SOURCE URL: {url}]\n{text[:15000]}\n"
    except Exception as e: return f"\nhttps://www.merriam-webster.com/dictionary/error: {e}\n"

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
                    # TABLE EXTRACTION (Re-integrated)
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table: p_text += " | ".join([str(c) if c else "[SPANNED]" for c in row]) + "\n"
                    # OCR FALLBACK
                    if ocr_enabled and (not p_text.strip() or len(p_text) < 100):
                        imgs = convert_from_bytes(f_bytes, first_page=i+1, last_page=i+1)
                        for img in imgs: p_text += f"\n[OCR]: {pytesseract.image_to_string(img)}\n"
                    text += f"\n[FILE: {file.name} | PAGE: {i+1}]\n{p_text}\n"
        elif ext in ["pptx", "pptm"]:
            prs = Presentation(file)
            for i, slide in enumerate(prs.slides):
                s_txt = ""
                for shape in slide.shapes:
                    if hasattr(shape, "text"): s_txt += shape.text + " "
                    # PPT TABLE EXTRACTION (Re-integrated)
                    if shape.has_table:
                        for row in shape.table.rows:
                            s_txt += " | ".join([c.text_frame.text if not c.is_spanned else "[SPANNED]" for c in row.cells]) + "\n"
                    # SCREENSHOT OCR
                    if ocr_enabled and shape.shape_type == 13:
                        img = Image.open(io.BytesIO(shape.image.blob))
                        s_txt += f"\n[SCREENSHOT OCR]: {pytesseract.image_to_string(img)}\n"
                text += f"\n[FILE: {file.name} | SLIDE: {i+1}]\n{s_txt}\n"
        elif ext == "docx":
            doc = DocxRead(file)
            text += "\n".join([p.text for p in doc.paragraphs])
    except Exception as e: st.error(f"Error reading {file.name}: {e}")
    return text

# --- Document Builders ---
def build_pdf(content, title):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Heading1'], fontSize=14, textColor=colors.white, backColor=colors.HexColor('#003366'), alignment=TA_LEFT, spaceAfter=12, borderPadding=5)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=14)
    elements = [Paragraph(f"TRAINING DESIGN DOCUMENT: {title}", styles['Title']), Spacer(1, 20)]
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if any(sec in line.upper() for sec in MANDATORY_SECTIONS) and "---" in line:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(line.replace('-', ''), header_style))
        else: elements.append(Paragraph(line, body_style))
    doc.build(elements); buf.seek(0); return buf

def build_word(content, title):
    doc = DocxDocument()
    doc.add_heading(f"Training Design Document: {title}", 0)
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if any(sec in line.upper() for sec in MANDATORY_SECTIONS) and "---" in line:
            doc.add_heading(line.replace('-', ''), level=1)
        else: doc.add_paragraph(line)
    buf = io.BytesIO(); doc.save(buf); buf.seek(0); return buf

# --- UI Setup ---
if "design_out" not in st.session_state: st.session_state.design_out = None
if "pdf_file" not in st.session_state: st.session_state.pdf_file = None
if "word_file" not in st.session_state: st.session_state.word_file = None

st.title("📘 Oracle Universal Design Agent")
with st.sidebar:
    st.title("🛠️ Settings")
    use_ocr = st.checkbox("Enable Vision/OCR", value=True)
    custom_bench = st.file_uploader("Upload Gold Standard (Reference)", type=["pdf", "docx"])

c1, c2 = st.columns(2)
pn = c1.text_input("Product Name", value="Oracle Cloud BICC")
ct = c1.selectbox("Course Type", ["eLearning", "Instructor-Led", "Blended"])
cn = c2.text_input("Course Title", placeholder="Build Smarter Reports with Oracle OTBI")
tr = c2.text_input("Target Job Roles", value="Data Analyst / BI Author")

jt = st.text_area("Job Task Analysis (Focus Areas)", placeholder="1. Create Analyses\n2. Visualize Data...")
url_inputs = st.text_area("🔗 Documentation URLs (Paste one link per line)")
files = st.file_uploader("📂 Source Documentation", type=["pdf", "pptx", "pptm", "docx"], accept_multiple_files=True)

# --- Orchestrator ---
if st.button("🚀 Generate Reliable Design", use_container_width=True):
    with st.status("🛠️ Analyzing Multi-Source Content...", expanded=True) as status:
        bench = extract_master_content(custom_bench, use_ocr) if custom_bench else "Follow standard Oracle Master Class ID principles."
        file_src = "".join([extract_master_content(f, use_ocr) for f in files])
        url_list = [u.strip() for u in url_inputs.split('\n') if u.strip()]
        url_src = "".join([extract_url_content(u) for u in url_list])
        all_knowledge = file_src + url_src
        
        try:
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            master_prompt = f"""
            ACT AS: Senior Oracle Instructional Designer. CONTEXT: {pn} | COURSE: {cn} | TYPE: {ct} | ROLES: {tr}
            JTA TASKS: {jt} | SOURCE DATA: {all_knowledge[:18000]} | BENCHMARK: {bench[:2000]}
            
            GOAL: Create a learner-centric TDD based on Oracle Master Class Standards.
            
            STRICT RULES:
            1. BALANCED MIX: Every module MUST include 1 Concept, 1 Demo, 1 Lab, and 1 Scenario.
            2. MICROLEARNING: Video topics must be 3-7 minutes. Total course seat time must be estimated.
            3. BLOOM'S Taxonomy: Configuration/Creation tasks = 'Applying' or 'Analyzing'. Use SMART verbs.
            4. 80/20 RULE: Prioritize highest-value skills and include a brief 80/20 rationale.
            5. GTM MESSAGE: Create a clear USP, explain business problems solved, and learner takeaways.
            6. TRACEABILITY: Cite [FILE: Name] or [URL: Link] for every claim. No invention.
            
            REQUIRED HEADERS:
            --- COURSE OVERVIEW, --- PERSONA INFORMATION, --- IMPLEMENTATION READINESS, --- GTM MESSAGING, --- COURSE COVERAGE TABLE, --- CASE STUDY, --- QA CHECKLIST.
            """
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": master_prompt}])
            st.session_state.design_out = res.choices[0].message.content
            st.session_state.pdf_file = build_pdf(st.session_state.design_out, cn)
            st.session_state.word_file = build_word(st.session_state.design_out, cn)
            status.update(label="✅ TDD Generated!", state="complete")
        except Exception as e: st.error(f"Brain Error: {e}")

# --- Display & Export ---
if st.session_state.design_out:
    audit = perform_reliability_audit(st.session_state.design_out)
    with st.expander("📊 Reliability Audit", expanded=True):
        st.metric("Traceability Tags Found", audit["traceability_tags"])
        for s, found in audit["sections"].items(): st.write(f"{'✅' if found else '❌'} {s}")
    
    col1, col2 = st.columns(2)
    col1.download_button("📄 Download PDF", data=st.session_state.pdf_file, file_name=f"{cn}_Design_Doc.pdf", use_container_width=True)
    col2.download_button("📝 Download Word", data=st.session_state.word_file, file_name=f"{cn}_Design_Doc.docx", use_container_width=True)
    st.markdown("---")
    st.markdown(st.session_state.design_out)
