"""Generate downloadable result files entirely in memory."""

from __future__ import annotations

import csv
import io
import json
from typing import Any
from xml.sax.saxutils import escape

from .models import ExtractionResult
from .scoring import MatchReport


def _report_data(extraction: ExtractionResult, match: MatchReport) -> dict[str, Any]:
    return {
        "overall_match_score": match.overall_score,
        "score_vector": {
            "required_skills": match.required_score,
            "preferred_skills": match.preferred_score,
            "experience": match.experience_score,
            "active_weight_shares": match.weight_shares,
        },
        "experience": {
            "candidate_years": match.experience_years,
            "minimum_required_years": match.minimum_experience_years,
        },
        "matched_skills": list(match.matched_skills),
        "missing_skills": list(match.missing_skills),
        "required_skill_results": [row.__dict__ for row in match.required],
        "preferred_skill_results": [row.__dict__ for row in match.preferred],
        "candidate_summary": extraction.candidate_summary,
    }


def _csv_bytes(data: dict[str, Any]) -> bytes:
    def safe_cell(value: Any) -> Any:
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["section", "item", "result", "score"])
    writer.writerow(["overall", "Match score", "", data["overall_match_score"]])
    for dimension, score in data["score_vector"].items():
        if dimension != "active_weight_shares":
            writer.writerow(["score vector", dimension, "", "" if score is None else score])
    for section, key in (("required skill", "required_skill_results"), ("preferred skill", "preferred_skill_results")):
        for row in data[key]:
            writer.writerow([section, safe_cell(row["skill"]), safe_cell(row["status"]), ""])
    writer.writerow(["experience", "Candidate years", data["experience"]["candidate_years"], ""])
    writer.writerow(["experience", "Minimum required years", data["experience"]["minimum_required_years"], ""])
    writer.writerow(["summary", safe_cell(data["candidate_summary"]), "", ""])
    return stream.getvalue().encode("utf-8-sig")


def _markdown_text(data: dict[str, Any]) -> str:
    lines = [
        "# Resume Match Report",
        "",
        f"**Overall match score:** {data['overall_match_score']}%",
        "",
        "## Score vector",
        "",
        "| Dimension | Score | Active weight |",
        "|---|---:|---:|",
    ]
    label_names = {
        "required_skills": "Required skills",
        "preferred_skills": "Preferred skills",
        "experience": "Experience",
    }
    for key, label in label_names.items():
        score = data["score_vector"][key]
        if score is not None:
            weight = data["score_vector"]["active_weight_shares"].get(label, 0)
            lines.append(f"| {label} | {score}% | {weight}% |")
    lines.extend(["", "## Required skills", ""])
    lines.extend(f"- {row['skill']}: {row['status']}" for row in data["required_skill_results"])
    lines.extend(["", "## Preferred skills", ""])
    lines.extend(f"- {row['skill']}: {row['status']}" for row in data["preferred_skill_results"])
    lines.extend(["", "## Experience", ""])
    years = data["experience"]["candidate_years"]
    minimum = data["experience"]["minimum_required_years"]
    lines.append(f"Candidate experience: {'Not found' if years is None else f'{years} years'}")
    lines.append(f"Minimum required: {'Not specified' if minimum is None else f'{minimum} years'}")
    lines.extend(["", "## Candidate summary", "", data["candidate_summary"], ""])
    return "\n".join(lines)


def _xlsx_bytes(data: dict[str, Any]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    def safe_cell(value: Any) -> Any:
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Match Summary"
    summary.append(["Resume Match Report"])
    summary.append(["Overall match score", data["overall_match_score"] / 100])
    summary["B2"].number_format = "0.0%"
    summary.append([])
    summary.append(["Score dimension", "Score", "Active weight"])
    labels = {
        "required_skills": "Required skills",
        "preferred_skills": "Preferred skills",
        "experience": "Experience",
    }
    for key, label in labels.items():
        score = data["score_vector"][key]
        if score is not None:
            summary.append([label, score / 100, data["score_vector"]["active_weight_shares"].get(label, 0) / 100])
            summary.cell(summary.max_row, 2).number_format = "0.0%"
            summary.cell(summary.max_row, 3).number_format = "0.0%"
    summary.append([])
    summary.append(["Candidate summary", safe_cell(data["candidate_summary"])])
    skills = workbook.create_sheet("Skills")
    skills.append(["Category", "Skill", "Status"])
    for category, key in (("Required", "required_skill_results"), ("Preferred", "preferred_skill_results")):
        for row in data[key]:
            skills.append([category, safe_cell(row["skill"]), safe_cell(row["status"])])
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = PatternFill("solid", fgColor="6C5CE7")
        for column in sheet.columns:
            column_letter = column[0].column_letter
            width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 14), 64)
            sheet.column_dimensions[column_letter].width = width
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _pdf_bytes(data: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=letter, rightMargin=0.65 * inch, leftMargin=0.65 * inch)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Resume Match Report", styles["Title"]),
        Spacer(1, 10),
        Paragraph(f"Overall match score: <b>{data['overall_match_score']}%</b>", styles["Heading2"]),
        Spacer(1, 8),
    ]
    vector_rows = [["Dimension", "Score", "Weight"]]
    for key, label in (("required_skills", "Required skills"), ("preferred_skills", "Preferred skills"), ("experience", "Experience")):
        score = data["score_vector"][key]
        if score is not None:
            weight = data["score_vector"]["active_weight_shares"].get(label, 0)
            vector_rows.append([label, f"{score}%", f"{weight}%"])
    story.append(Table(vector_rows, style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#201A3A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C5C0D6")),
        ("PADDING", (0, 0), (-1, -1), 7),
    ])))
    for title, key in (("Required skills", "required_skill_results"), ("Preferred skills", "preferred_skill_results")):
        story.extend([Spacer(1, 12), Paragraph(title, styles["Heading2"])])
        rows = [["Skill", "Status"]] + [[escape(row["skill"]), escape(row["status"])] for row in data[key]]
        if len(rows) == 1:
            rows.append(["No skills listed", ""])
        story.append(Table(rows, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#201A3A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C5C0D6")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])))
    story.extend([Spacer(1, 12), Paragraph("Candidate summary", styles["Heading2"]), Paragraph(escape(data["candidate_summary"]), styles["BodyText"])])
    document.build(story)
    return output.getvalue()


def build_download(data_format: str, extraction: ExtractionResult, match: MatchReport) -> tuple[bytes, str, str]:
    """Return bytes, filename, MIME type for a selected export format."""

    data = _report_data(extraction, match)
    if data_format == "JSON":
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "resume_match_report.json", "application/json"
    if data_format == "CSV":
        return _csv_bytes(data), "resume_match_report.csv", "text/csv"
    if data_format == "Excel workbook":
        return _xlsx_bytes(data), "resume_match_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if data_format == "PDF":
        return _pdf_bytes(data), "resume_match_report.pdf", "application/pdf"
    return _markdown_text(data).encode("utf-8"), "resume_match_report.md", "text/markdown"

