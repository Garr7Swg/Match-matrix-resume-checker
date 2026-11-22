"""Streamlit dashboard for structured resume extraction and job matching."""

from __future__ import annotations

import streamlit as st

from resume_matcher.extractors import DocumentProcessingError, extract_document_text
from resume_matcher.llm import ExtractionError, extract_structured_data
from resume_matcher.reports import build_download
from resume_matcher.scoring import MatchReport, calculate_match


APP_TITLE = "MATCH//MATRIX"
FAILURE_MESSAGE = "document processing failed, try again"
IRRELEVANT_MESSAGE = "please upload documents only regarding any job or job market"
SUPPORTED_TYPES = [
    "pdf", "docx", "odt", "txt", "md", "rtf", "html", "htm", "xml", "csv", "json",
    "xlsx", "pptx", "png", "jpg", "jpeg", "tif", "tiff", "bmp",
]


st.set_page_config(
    page_title="Match//Matrix — Resume Matcher",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def clear_session() -> None:
    for key in ("resume_upload", "job_description", "provider", "model_name", "api_key_input"):
        st.session_state.pop(key, None)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root { --ink:#edf1ff; --muted:#a4abc1; --panel:#111421; --line:#272b40; --cyan:#61f3e3; --violet:#a78bfa; }
    .stApp { background: radial-gradient(ellipse at 85% 2%, #281d4a 0%, transparent 30%), #080a11; color:var(--ink); }
    html, body, [class*="css"] { font-family:'Space Grotesk',sans-serif; }
    h1,h2,h3 { letter-spacing:-.035em; }
    .block-container { padding-top:2rem; max-width:1440px; }
    [data-testid="stSidebar"] { background:#0d1019; border-right:1px solid var(--line); }
    [data-testid="stMetric"] { background:linear-gradient(135deg,#151a29,#111421); border:1px solid #292e46; border-radius:16px; padding:18px 20px; }
    [data-testid="stMetricLabel"] { color:#a4abc1; }
    [data-testid="stMetricValue"] { color:var(--cyan); font-family:'DM Mono',monospace; }
    .hero { border:1px solid #34304e; background:linear-gradient(115deg,rgba(23,27,44,.96),rgba(19,17,37,.87)); border-radius:24px; padding:30px 34px; margin-bottom:22px; box-shadow:0 0 50px rgba(136,91,255,.08); }
    .eyebrow { font-family:'DM Mono',monospace; color:var(--cyan); font-size:12px; letter-spacing:.14em; }
    .hero-title { font-size:clamp(30px,4vw,48px); font-weight:700; line-height:1.06; margin:10px 0; }
    .hero-copy { color:var(--muted); max-width:750px; font-size:16px; }
    .section-card { background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:20px 22px; }
    .tiny-label { color:var(--muted); font-family:'DM Mono',monospace; font-size:11px; letter-spacing:.1em; text-transform:uppercase; }
    .score-wrap { background:radial-gradient(circle at 50% 50%,#1e2440 0,#121624 66%); border:1px solid #33314f; border-radius:20px; padding:22px; text-align:center; }
    .score-number { color:var(--cyan); font:500 52px 'DM Mono',monospace; text-shadow:0 0 22px rgba(97,243,227,.25); }
    .score-caption { color:var(--muted); font-size:12px; letter-spacing:.12em; text-transform:uppercase; }
    .pill { display:inline-block; padding:5px 10px; border-radius:99px; font:11px 'DM Mono',monospace; margin:2px 4px 2px 0; }
    .matched { color:#68f3d7; background:rgba(41,194,155,.11); border:1px solid rgba(41,194,155,.3); }
    .missing { color:#ff9eaf; background:rgba(239,88,116,.1); border:1px solid rgba(239,88,116,.28); }
    div.stButton > button, div.stDownloadButton > button { border-radius:11px; border:1px solid #6151a8; background:linear-gradient(100deg,#684bd6,#4f74d8); color:white; font-weight:600; }
    div.stButton > button:hover, div.stDownloadButton > button:hover { border-color:var(--cyan); color:white; box-shadow:0 0 20px rgba(97,243,227,.16); }
    div[data-testid="stForm"] { background:#111421; border:1px solid var(--line); border-radius:18px; padding:20px; }
    .disclaimer { color:#9199b1; font-size:12px; border-left:2px solid #7261d8; padding:8px 12px; background:rgba(90,73,160,.08); border-radius:0 8px 8px 0; }
    .stCaption { color:#949bb2; }
    </style>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.markdown("### ✦ Match//Matrix")
    st.caption("Structured extraction · deterministic scoring")
    st.divider()
    provider = st.selectbox("AI provider", ["Groq", "OpenAI"], key="provider")
    default_model = "openai/gpt-oss-20b" if provider == "Groq" else "gpt-4o-mini"
    model_name = st.text_input("Model", value=default_model, key="model_name")
    api_key = st.text_input(
        f"{provider} API key",
        type="password",
        placeholder="Enter for this session",
        key="api_key_input",
    )
    st.caption("Your API key is held in this browser session's app memory and is not written to a file.")
    st.divider()
    st.markdown(
        '<div class="disclaimer">Cold starts can take 30–60 seconds because this demo uses free API tiers and lightweight app hardware.</div>',
        unsafe_allow_html=True,
    )
    st.caption("Resume text and job description are sent to the selected AI provider for extraction. This app does not save them to a database or file.")
    st.button("Clear session data", on_click=clear_session, use_container_width=True)


st.markdown(
    f"""
    <div class="hero">
      <div class="eyebrow">CAREER INTELLIGENCE / 01</div>
      <div class="hero-title">{APP_TITLE}<br><span style="color:#61f3e3">Make the fit visible.</span></div>
      <div class="hero-copy">Turn a resume and a role brief into validated structured data, skill coverage, and a transparent match score. The model extracts facts; the scoring engine does the math.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="disclaimer">Cold starts may take 30–60 seconds because this demo relies on free API tiers and lightweight hardware.</div>',
    unsafe_allow_html=True,
)

st.markdown("#### Build a match")
st.caption("Upload one candidate document and paste the job description. Common document, office, PDF, and image formats are supported.")

with st.form("match_form", clear_on_submit=False):
    uploaded_file = st.file_uploader(
        "Resume or job-application document",
        type=SUPPORTED_TYPES,
        help="Supported: PDF, DOCX, ODT, TXT, Markdown, RTF, HTML/XML, CSV, JSON, XLSX, PPTX, and PNG/JPEG/TIFF/BMP images.",
        key="resume_upload",
    )
    job_description = st.text_area(
        "Job description",
        height=205,
        placeholder="Paste the complete job description, including required and preferred qualifications…",
        key="job_description",
    )
    submitted = st.form_submit_button("Analyze match  →", use_container_width=True)


def render_skill_rows(rows: tuple, *, empty_message: str) -> None:
    if not rows:
        st.caption(empty_message)
        return
    for row in rows:
        badge = "matched" if row.status == "Matched" else "missing"
        st.markdown(f'<span class="pill {badge}">{row.status.upper()}</span> {row.skill}', unsafe_allow_html=True)


def render_result(extraction, match: MatchReport) -> None:
    st.markdown("---")
    st.markdown("#### Match overview")
    metric_cols = st.columns([1.05, 1, 1, 1])
    with metric_cols[0]:
        st.markdown(
            f'<div class="score-wrap"><div class="score-number">{match.overall_score:.1f}%</div><div class="score-caption">Deterministic fit</div></div>',
            unsafe_allow_html=True,
        )
    with metric_cols[1]:
        st.metric("Required skill fit", "N/A" if match.required_score is None else f"{match.required_score:.1f}%")
    with metric_cols[2]:
        st.metric("Preferred skill fit", "N/A" if match.preferred_score is None else f"{match.preferred_score:.1f}%")
    with metric_cols[3]:
        st.metric("Experience fit", "N/A" if match.experience_score is None else f"{match.experience_score:.1f}%")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### Required skills")
        render_skill_rows(match.required, empty_message="No required skills were identified.")
        st.markdown("##### Preferred skills")
        render_skill_rows(match.preferred, empty_message="No preferred skills were identified.")
    with right:
        st.markdown("##### Experience alignment")
        years = "Not found" if match.experience_years is None else f"{match.experience_years:g} years"
        minimum = "Not specified" if match.minimum_experience_years is None else f"{match.minimum_experience_years:g} years"
        st.markdown(f"**Resume estimate:** {years}  \n**Role minimum:** {minimum}")
        st.markdown("##### Candidate snapshot")
        st.write(extraction.candidate_summary or "No summary available.")

    st.markdown("##### Score vector")
    active = [(name, share) for name, share in match.weight_shares.items()]
    st.caption("Overall = weighted average of the dimensions present. Base weights: required skills 70%, preferred skills 20%, experience 10%; unavailable dimensions are omitted and active weights are normalized.")
    vector_cols = st.columns(max(1, len(active)))
    scores = {
        "Required skills": match.required_score,
        "Preferred skills": match.preferred_score,
        "Experience": match.experience_score,
    }
    for column, (name, share) in zip(vector_cols, active):
        with column:
            value = scores[name]
            st.markdown(f"<div class='section-card'><div class='tiny-label'>{name}</div><h3>{value:.1f}%</h3><span class='stCaption'>weight {share:.1f}%</span></div>", unsafe_allow_html=True)

    st.markdown("##### Download result")
    formats = ["JSON", "CSV", "Excel workbook", "PDF", "Markdown"]
    selected_format = st.selectbox("Result format", formats, label_visibility="collapsed", key="export_format")
    try:
        file_bytes, filename, mime_type = build_download(selected_format, extraction, match)
        st.download_button(
            f"Download {selected_format}",
            data=file_bytes,
            file_name=filename,
            mime=mime_type,
            on_click="ignore",
            use_container_width=True,
        )
    except Exception:
        st.error(FAILURE_MESSAGE)


if submitted:
    if uploaded_file is None or not job_description.strip():
        st.warning("Upload a candidate document and paste a job description to continue.")
    elif not api_key.strip() or not model_name.strip():
        st.warning("Enter an API key and model name in the sidebar to continue.")
    elif len(job_description) > 20_000:
        st.error(FAILURE_MESSAGE)
    else:
        try:
            resume_text = extract_document_text(uploaded_file.name, uploaded_file.getvalue())
            extraction = extract_structured_data(
                provider=provider,
                api_key=api_key.strip(),
                model=model_name.strip(),
                resume_text=resume_text,
                job_description=job_description.strip(),
            )
            if not extraction.candidate_document_is_job_related or not extraction.job_description_is_job_related:
                st.error(IRRELEVANT_MESSAGE)
            else:
                match = calculate_match(extraction)
                render_result(extraction, match)
        except (DocumentProcessingError, ExtractionError, ValueError):
            st.error(FAILURE_MESSAGE)
        except Exception:
            st.error(FAILURE_MESSAGE)

