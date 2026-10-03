"""Excel export for shortlisted / screened candidates.

Generates a real .xlsx file (pandas + openpyxl) with three sheets:
Shortlisted Candidates, Assessment Summary, Job Requirements.
"""

from __future__ import annotations

import re
from typing import List

import pandas as pd
from openpyxl.utils import get_column_letter

from schemas import CandidateAssessment, JobRequirements


def sanitize_filename(job_title: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", job_title or "Role").strip("_")
    base = base or "Role"
    return f"{base}_Shortlisted_Candidates.xlsx"


def format_experience(years) -> str:
    if years is None:
        return ""
    try:
        return f"{float(years):.1f} yrs"
    except (TypeError, ValueError):
        return str(years)


def _ranked(results: List[CandidateAssessment]) -> List[CandidateAssessment]:
    """Highest overall_match_score first. Ties keep their original
    (insertion) order rather than inventing artificial precision."""
    indexed = list(enumerate(results))
    indexed.sort(key=lambda pair: (-pair[1].overall_match_score, pair[0]))
    return [r for _, r in indexed]


def _autosize(ws, df: pd.DataFrame) -> None:
    for idx, col in enumerate(df.columns, start=1):
        if len(df):
            max_len = max([len(str(col))] + [len(str(v)) for v in df[col].tolist()])
        else:
            max_len = len(str(col))
        ws.column_dimensions[get_column_letter(idx)].width = min(max(12, max_len + 2), 60)


def build_excel(
    all_results: List[CandidateAssessment],
    jd: JobRequirements,
    top_n: int,
    output_path: str,
) -> str:
    ranked = _ranked(all_results)
    shortlist = ranked[: max(top_n, 0)]

    # ---- Sheet 1: Shortlisted Candidates ----
    sheet1_cols = [
        "Rank", "Name", "Phone Number", "Email", "Match Score",
        "Recommendation", "Current Role", "Current Company",
        "Experience", "Current Location",
    ]
    sheet1_rows = []
    for rank, r in enumerate(shortlist, start=1):
        sheet1_rows.append({
            "Rank": rank,
            "Name": r.candidate_name or "",
            "Phone Number": r.phone_number or "",
            "Email": r.email or "",
            "Match Score": r.overall_match_score,
            "Recommendation": r.recommendation,
            "Current Role": r.current_role or "",
            "Current Company": r.current_company or "",
            "Experience": format_experience(r.total_experience_years),
            "Current Location": r.current_location or "",
        })
    df1 = pd.DataFrame(sheet1_rows, columns=sheet1_cols)

    # ---- Sheet 2: Assessment Summary (ALL screened candidates) ----
    sheet2_cols = [
        "Rank", "Name", "Required Skills Score", "Preferred Skills Score",
        "Experience Score", "Role Relevance Score", "Education Score",
        "Industry Relevance Score", "Strengths", "Gaps",
        "Missing Information", "Assessment Reason",
    ]
    sheet2_rows = []
    for rank, r in enumerate(ranked, start=1):
        sheet2_rows.append({
            "Rank": rank,
            "Name": r.candidate_name or "",
            "Required Skills Score": r.required_skills_score,
            "Preferred Skills Score": r.preferred_skills_score,
            "Experience Score": r.experience_score,
            "Role Relevance Score": r.role_relevance_score,
            "Education Score": r.education_score,
            "Industry Relevance Score": r.industry_relevance_score,
            "Strengths": "; ".join(r.strengths),
            "Gaps": "; ".join(r.gaps),
            "Missing Information": "; ".join(r.missing_information),
            "Assessment Reason": r.assessment_reason,
        })
    df2 = pd.DataFrame(sheet2_rows, columns=sheet2_cols)

    # ---- Sheet 3: Job Requirements ----
    jd_dict = jd.model_dump()
    sheet3_rows = []
    for key, value in jd_dict.items():
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value)
        sheet3_rows.append({
            "Requirement": key.replace("_", " ").title(),
            "Value": value if value is not None else "",
        })
    df3 = pd.DataFrame(sheet3_rows, columns=["Requirement", "Value"])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df1.to_excel(writer, sheet_name="Shortlisted Candidates", index=False)
        df2.to_excel(writer, sheet_name="Assessment Summary", index=False)
        df3.to_excel(writer, sheet_name="Job Requirements", index=False)

        _autosize(writer.sheets["Shortlisted Candidates"], df1)
        _autosize(writer.sheets["Assessment Summary"], df2)
        _autosize(writer.sheets["Job Requirements"], df3)

    return output_path
