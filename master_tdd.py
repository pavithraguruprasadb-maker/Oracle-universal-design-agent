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

# PDF & Word Generation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from docx import Document as DocxDocument

# --- Configuration ---
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
- TRACEABILITY: Cite [FILE:...] or [URL:...] for every module.
- MAPPING: JTA tasks must link to Bloom objectives.
- CONSULTANT LEVEL: Focus on implementation, not just 'how-to'.
"""

st.set_page_config(page_title="Universal Design Agent", page_icon="📘", layout="wide")

# --- Logic: Reliability Audit ---
def perform_reliability_audit(text):
    audit = {"sections": {}, "traceability_tags": 0}
    for sec in MANDATORY_SECTIONS:
        found = re.search(rf"---?\s*{sec}", text, re.IGNORECASE)
        audit["sections"][sec] = True if found else False
    tags = re.findall(r"\[(FILE|URL):.*?\]", text)
    audit["traceability_tags"] = len(tags)
    return audit

# --- Logic: Web Scraper ---
def extract_url_content(url):
    if not url: return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for s in soup(["script", "style"]): s.decompose()
        text = re.sub(r'\s+', ' ', soup.get_text()).strip()
        return f"\n[SOURCE URL: {url}]\n{text[:15000]}\n"
    except Exception as e:
        return f"\nhttps://www.merriam-webster.com/dictionary/error: {e}\n"

# --- Logic: Multi-Source Extraction (With Vision/OCR) ---
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
                    if ocr_enabled and shape.shape_type == 13: # Picture
                        img = Image.open(io.BytesIO(shape.image.blob))
                        s_txt += f"\n[SCREENSHOT OCR]: {pytesseract.image_to_string(img)}\n"
                text += f"\n[FILE: {file.name} | SLIDE: {i+1}]\n{s_txt}\n"
        elif ext == "docx":
            doc = DocxRead(file)
            text += "\n".join([p.text for p in doc.paragraphs])
    except Exception as e: st.error(f"Error reading {file.name}: {e}")
    return text

# --- UI ---
st.sidebar.title("🛠️ Agent Controls")
use_ocr = st.sidebar.checkbox("Enable Vision/OCR", value=True)
custom_bench = st.sidebar.file_uploader("Upload Gold Standard", type=["pdf", "pptx", "docx"])

if "design_out" not in st.session_state: st.session_state.design_out = None

st.title("📘 Universal Design Agent")
c1, c2 = st.columns(2)
pn = c1.text_input("Product Pillar", value="Oracle Cloud EPM")
cn = c2.text_input("Course Title", placeholder="e.g. Predictive Cash Forecasting")
url_input = st.text_input("🔗 Documentation URL", placeholder="Paste Oracle Help Center link here...")
jt = st.text_area("Job Task Analysis (JTA)")
files = st.file_uploader("📂 Source Files", type=["pdf", "pptx", "pptm", "docx"], accept_multiple_files=True)

# --- Orchestrator ---
if st.button("🚀 Generate Reliable Design", use_container_width=True):
    with st.status("🛠️ Analyzing Multi-Source Knowledge...", expanded=True) as status:
        bench = extract_master_content(custom_bench, use_ocr) if custom_bench else GOLD_STANDARD_FALLBACK
        all_src = "".join([extract_master_content(f, use_ocr) for f in files]) + extract_url_content(url_input)
        
        try:
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            prompt = f"""
            ACT AS: Senior Oracle Instructional Designer. AUDIENCE: Functional Consultants.
            SOURCE DATA: {all_src[:15000]} | BENCHMARK: {bench[:2000]}
            INPUTS: {pn}, {cn}, {jt}
            RULES:
            1. Use exact headers: --- COURSE OVERVIEW, --- JOB TASK TO SKILL MAPPING, etc.
            2. For configuration tasks, use Bloom's 'Applying' or 'Analyzing'.
            3. Include a 'Troubleshooting' topic in the table.
            4. Cite [FILE: Name] or [URL: Link] for every claim.
            """
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
            st.session_state.design_out = res.choices[0].message.content
            status.update(label="✅ Generation Complete!", state="complete")
        except Exception as e: st.error(f"Brain Error: {e}")

# --- Results ---
if st.session_state.design_out:
    audit = perform_reliability_audit(st.session_state.design_out)
    with st.expander("📊 Reliability Audit", expanded=True):
        st.metric("Traceability Tags", audit["traceability_tags"])
        for s, found in audit["sections"].items(): st.write(f"{'✅' if found else '❌'} {s}")
    st.markdown("---")
    st.markdown(st.session_state.design_out)
