"""Excel HR Consultancy -- AI-Assisted CV Screening.

Run with:
    streamlit run app.py

Uses the user's locally-authenticated Claude Code CLI (`claude -p ...`)
for all AI reasoning. No Anthropic API key, database, or cloud service
is used. Everything lives in Streamlit session state for the current
session only.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

import claude_engine
import exports
import parsers
from schemas import CandidateAssessment, JobRequirements

TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)

PRIMARY = "#0C404E"
SECONDARY = "#57757C"
BG = "#F7FAFB"

st.set_page_config(page_title="Excel HR Consultancy — AI-Assisted CV Screening", layout="wide")

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {BG}; }}
    h1, h2, h3 {{ color: {PRIMARY}; }}
    div.stButton > button {{
        background-color: {PRIMARY};
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1.2rem;
    }}
    div.stButton > button:hover {{ background-color: {SECONDARY}; color: white; }}
    div[data-testid="stDownloadButton"] > button {{
        background-color: {PRIMARY};
        color: white;
        font-weight: 600;
        padding: 0.7rem 1.4rem;
    }}
    .step-card {{
        background: white;
        border: 1px solid #E1E8EA;
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1.2rem;
    }}
    .step-label {{
        display: inline-block;
        background: {PRIMARY};
        color: white;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.15rem 0.6rem;
        border-radius: 4px;
        margin-bottom: 0.6rem;
        letter-spacing: 0.04em;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- Session state ----------------
_defaults = {
    "jd_text": "",
    "jd_requirements": None,
    "top_n": 10,
    "results": [],
    "screening_errors": [],
    "screening_done": False,
}
for _k, _v in _defaults.items():
    st.session_state.setdefault(_k, _v)


def save_upload(uploaded_file) -> str:
    ext = Path(uploaded_file.name).suffix
    dest = TEMP_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(dest)


def cleanup_temp() -> None:
    for f in TEMP_DIR.glob("*"):
        if f.name == ".gitkeep":
            continue
        try:
            f.unlink()
        except OSError:
            pass


# ---------------- Header ----------------
st.title("Excel HR Consultancy")
st.subheader("AI-Assisted CV Screening")
st.write("Upload a Job Description and candidate CVs to identify candidates for recruiter review.")

claude_ok, claude_msg = claude_engine.check_claude()
if not claude_ok:
    st.error("Claude Code is not installed or authenticated. Open Terminal and run `claude` first.")
    st.caption(f"Details: {claude_msg}")
    st.stop()
st.caption(f"Claude Code detected — {claude_msg}")

st.divider()

# ================= STEP 1: JD =================
st.markdown('<div class="step-card">', unsafe_allow_html=True)
st.markdown('<span class="step-label">STEP 1</span>', unsafe_allow_html=True)
st.markdown("### Upload Job Description")

jd_mode = st.radio("Provide the JD by:", ["Upload file", "Paste text"], horizontal=True, label_visibility="collapsed")

jd_raw_text = ""
if jd_mode == "Upload file":
    jd_file = st.file_uploader("Upload Job Description", type=["pdf", "docx", "txt"], key="jd_file")
    if jd_file is not None:
        jd_path = save_upload(jd_file)
        extracted = parsers.extract_document_text(jd_path)
        if extracted is None:
            st.error("Could not extract readable text from this Job Description file.")
        else:
            jd_raw_text = extracted
else:
    jd_raw_text = st.text_area("Paste Job Description", height=220, key="jd_paste", label_visibility="collapsed", placeholder="Paste the full Job Description text here...")

analyse_clicked = st.button("Analyse Job Description", disabled=not jd_raw_text.strip())

if analyse_clicked and jd_raw_text.strip():
    with st.spinner("Claude is reading the Job Description..."):
        jd_req, err = claude_engine.analyse_job_description(jd_raw_text)
    if jd_req is None:
        st.error(f"Could not analyse the Job Description: {err}")
    else:
        st.session_state.jd_requirements = jd_req
        st.session_state.jd_text = jd_raw_text
        st.session_state.results = []
        st.session_state.screening_errors = []
        st.session_state.screening_done = False
        st.success("Job Description analysed.")

if st.session_state.jd_requirements is not None:
    jd: JobRequirements = st.session_state.jd_requirements
    with st.expander("Review extracted JD requirements", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Job Title:** {jd.job_title or '—'}")
            st.markdown(f"**Department:** {jd.department or '—'}")
            st.markdown(f"**Location:** {jd.location or '—'}")
            st.markdown(f"**Work Mode:** {jd.work_mode or '—'}")
            exp_min = jd.min_experience_years if jd.min_experience_years is not None else "—"
            exp_max = jd.max_experience_years if jd.max_experience_years is not None else "—"
            st.markdown(f"**Experience:** {exp_min} to {exp_max} yrs")
            st.markdown(f"**Notice Period:** {jd.notice_period or '—'}")
        with c2:
            st.markdown(f"**Required Skills:** {', '.join(jd.required_skills) or '—'}")
            st.markdown(f"**Preferred Skills:** {', '.join(jd.preferred_skills) or '—'}")
            st.markdown(f"**Education:** {', '.join(jd.education_requirements) or '—'}")
            st.markdown(f"**Certifications:** {', '.join(jd.certifications) or '—'}")
            st.markdown(f"**Industry Experience:** {', '.join(jd.industry_experience) or '—'}")
        st.markdown(f"**Mandatory Requirements:** {', '.join(jd.mandatory_requirements) or '—'}")
        st.markdown(f"**Preferred Requirements:** {', '.join(jd.preferred_requirements) or '—'}")
        st.markdown(f"**Knockout Requirements:** {', '.join(jd.knockout_requirements) or '—'}")
        if jd.notes:
            st.info(jd.notes)

st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.jd_requirements is None:
    st.stop()

# ================= STEP 2: Top N =================
st.markdown('<div class="step-card">', unsafe_allow_html=True)
st.markdown('<span class="step-label">STEP 2</span>', unsafe_allow_html=True)
st.markdown("### How many candidates would you like to shortlist?")
st.session_state.top_n = st.number_input("Top Candidates", min_value=1, value=int(st.session_state.top_n), step=1)
st.markdown("</div>", unsafe_allow_html=True)

# ================= STEP 3: CVs =================
st.markdown('<div class="step-card">', unsafe_allow_html=True)
st.markdown('<span class="step-label">STEP 3</span>', unsafe_allow_html=True)
st.markdown("### Upload Candidate CVs")
cv_files = st.file_uploader(
    "Upload Candidate CVs", type=["pdf", "docx"], accept_multiple_files=True, key="cv_files"
)
if cv_files:
    st.caption(f"Selected: {len(cv_files)} CVs")

start_clicked = st.button("Start CV Screening", disabled=not cv_files)
st.markdown("</div>", unsafe_allow_html=True)

# ================= SCREENING =================
if start_clicked and cv_files:
    jd = st.session_state.jd_requirements
    st.session_state.results = []
    st.session_state.screening_errors = []
    st.session_state.screening_done = False

    st.markdown('<div class="step-card">', unsafe_allow_html=True)
    st.caption(
        "To stop early, use the ⏹ stop control shown while this app is running — "
        "CVs already screened will be kept."
    )
    progress = st.progress(0)
    status = st.empty()
    total = len(cv_files)
    completed = 0
    failed = 0

    for i, uploaded in enumerate(cv_files, start=1):
        status.markdown(
            f"**Screening CVs — {completed + failed}/{total} completed**\n\n"
            f"Currently screening: `{uploaded.name}`  \n"
            f"Completed: {completed}  ·  Failed: {failed}"
        )
        try:
            cv_path = save_upload(uploaded)
            cv_text = parsers.extract_document_text(cv_path)

            if cv_text is None:
                r = CandidateAssessment(
                    source_file=uploaded.name,
                    extraction_note=parsers.NO_TEXT_MARKER,
                    recommendation="Not a Match",
                    confidence="Low",
                    assessment_reason="No readable text could be extracted from this file.",
                )
                st.session_state.results.append(r)
                failed += 1
            else:
                assessment, err = claude_engine.analyse_candidate(jd, cv_text, st.session_state.jd_text)
                if assessment is None:
                    st.session_state.screening_errors.append(f"{uploaded.name}: {err}")
                    failed += 1
                else:
                    assessment.source_file = uploaded.name
                    st.session_state.results.append(assessment)
                    completed += 1
        except Exception as exc:  # noqa: BLE001
            st.session_state.screening_errors.append(f"{uploaded.name}: unexpected error ({exc})")
            failed += 1

        progress.progress(i / total)

    status.markdown(f"**Screening complete.** Completed: {completed} · Failed: {failed}")
    st.session_state.screening_done = True
    cleanup_temp()
    st.markdown("</div>", unsafe_allow_html=True)

# ================= STEP 4: RESULTS =================
if st.session_state.screening_done and st.session_state.results:
    st.markdown('<div class="step-card">', unsafe_allow_html=True)
    st.markdown('<span class="step-label">STEP 4</span>', unsafe_allow_html=True)
    st.markdown("### Screening Results")

    results = st.session_state.results
    ranked = sorted(enumerate(results), key=lambda pair: (-pair[1].overall_match_score, pair[0]))
    ranked = [r for _, r in ranked]
    top_n = int(st.session_state.top_n)

    if st.session_state.screening_errors:
        with st.expander(f"{len(st.session_state.screening_errors)} CV(s) could not be screened"):
            for e in st.session_state.screening_errors:
                st.write(f"- {e}")

    table_rows = []
    for rank, r in enumerate(ranked, start=1):
        flag = " ⚠" if r.mandatory_requirements_missing else ""
        table_rows.append({
            "Rank": rank,
            "Candidate": (r.candidate_name or "Unknown") + flag,
            "Match Score": r.overall_match_score,
            "Recommendation": r.recommendation,
            "Experience": exports.format_experience(r.total_experience_years),
            "Current Role": r.current_role or "",
            "Current Company": r.current_company or "",
            "Phone": r.phone_number or "",
            "Email": r.email or "",
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    st.caption("⚠ = one or more mandatory requirements are missing for this candidate.")
    st.markdown(f"**Recommended shortlist:** top {min(top_n, len(ranked))} of {len(ranked)} screened candidates.")

    for rank, r in enumerate(ranked, start=1):
        with st.expander(f"{rank}. {r.candidate_name or 'Unknown'} — {r.overall_match_score}"):
            cols = st.columns(3)
            cols[0].metric("Overall Match", r.overall_match_score)
            cols[1].metric("Required Skills", r.required_skills_score)
            cols[2].metric("Experience Score", r.experience_score)
            st.write(f"**Recommendation:** {r.recommendation}  ·  **Confidence:** {r.confidence}")
            st.write(f"**Strengths:** {', '.join(r.strengths) or '—'}")
            st.write(f"**Gaps:** {', '.join(r.gaps) or '—'}")
            st.write(f"**Missing information:** {', '.join(r.missing_information) or '—'}")
            if r.mandatory_requirements_missing:
                st.warning(f"Mandatory requirements missing: {', '.join(r.mandatory_requirements_missing)}")
            st.write(f"**Assessment reason:** {r.assessment_reason or '—'}")
            if r.extraction_note:
                st.error(r.extraction_note)

    st.markdown("</div>", unsafe_allow_html=True)

    # ================= STEP 5/6: EXCEL =================
    st.markdown('<div class="step-card">', unsafe_allow_html=True)
    st.markdown('<span class="step-label">STEP 5</span>', unsafe_allow_html=True)
    st.markdown("### Download Shortlist")

    jd = st.session_state.jd_requirements
    filename = exports.sanitize_filename(jd.job_title)
    out_path = TEMP_DIR / filename
    exports.build_excel(ranked, jd, top_n, str(out_path))

    with open(out_path, "rb") as f:
        excel_bytes = f.read()

    st.download_button(
        "Download Shortlisted Candidates Excel",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption("This decision-support shortlist is for recruiter review, not an automatic hiring decision.")
    st.markdown("</div>", unsafe_allow_html=True)
