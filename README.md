# Match//Matrix — Structured Data Extraction & AI Resume Matcher

A local-first Streamlit dashboard that turns a candidate document and a job description into validated structured data, a skill coverage vector, and downloadable results.

The model extracts facts. Pydantic validates the response. Python computes every score deterministically. The app does not write resumes, job descriptions, reports, or API keys to disk or a database. Uploaded bytes, parsed text, API key, and results exist in app/session memory while in use. Resume text and the job description are sent to the selected OpenAI or Groq API for extraction; check that provider's data handling terms before using sensitive documents.

> Cold starts can take 30–60 seconds because the demo is designed around free API tiers and lightweight app hardware. API rate limits or provider errors display: `document processing failed, try again`.

## What it does

- Accepts PDF, DOCX, ODT, TXT, Markdown, RTF, HTML/XML, CSV, JSON, XLSX, PPTX, and common image files.
- Extracts text in memory, then asks OpenAI or Groq for skills, supporting evidence, and experience fields.
- Requests JSON Object Mode (`response_format={"type": "json_object"}`) and validates the response against a strict Pydantic schema (`extra="forbid"`, strict types).
- Rejects irrelevant documents with: `please upload documents only regarding any job or job market`.
- Scores required skills (70%), preferred skills (20%), and minimum experience (10%). Dimensions absent from the job description are omitted and the remaining weights are normalized. Skill coverage is exact after conservative name normalization; experience is capped at 100% once the stated minimum is met. The weighted vector and formula are visible in the UI. The LLM never returns a match percentage.
- Exports results as JSON, CSV, XLSX, PDF, or Markdown, generated in memory.
- Has no login, database, file writes, or content logging. Use **Clear session data** to clear the uploader and key widget state, or close the browser tab to end the session.

## Local setup

### 1. Use Python and create a virtual environment

This project targets **CPython 3.12 and 3.13**. `pyproject.toml` declares `requires-python = ">=3.12,<3.14"`, so installation will reject other Python versions. The dependency bounds are kept in that same file; `requirements.txt` installs the project and its dependencies.

From the project directory, use Python 3.12:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

To use Python 3.13 instead, create the environment with `py -3.13 -m venv .venv`, then run the same activation and installation commands. Use one Python version per virtual environment; recreate `.venv` when switching versions.

If PowerShell blocks virtual environment activation, run this once in that terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

### 2. (Optional) Enable OCR for image resumes

The Python package calls the Tesseract executable. Install Tesseract OCR separately and ensure `tesseract.exe` is on `PATH`. If that executable is unavailable, image processing returns the generic document-processing error. PDF text extraction does not require OCR; scanned PDFs may need to be OCR'd before upload.

### 3. Run the app

```powershell
streamlit run app.py
```

Choose Groq or OpenAI in the sidebar, enter that provider's API key and model name for the session, upload a document, and paste the job description. No key is required to start the UI.

This setup uses the API for model inference, so the RTX 2060 is not required or used by default. The local CPU handles parsing and report generation; the stated i7/16 GB system is sufficient for the dashboard. Provider limits, latency, and pricing apply.

Groq's current JSON-mode default in the sidebar is `openai/gpt-oss-20b`; OpenAI's default is `gpt-4o-mini`. Model availability can change, so the model field is editable. The app uses JSON Object Mode for broad compatibility. JSON mode guarantees JSON syntax rather than schema adherence, so Pydantic validation remains mandatory and a malformed response is treated as a processing failure.

## Coding walkthrough

1. **Define the response contract** in `resume_matcher/models.py`. `ExtractionResult` names every accepted output field; nested `SkillEvidence` requires evidence. `extra="forbid"` prevents surprise fields, and strict validation catches wrong types.
2. **Parse candidate documents** in `resume_matcher/extractors.py`. Each parser receives bytes and uses memory streams. The code covers text, office, PDF, and image formats without saving uploads to disk. Size, page, and extracted-text limits bound resource use.
3. **Call the model** in `resume_matcher/llm.py`. The provider adapter uses the OpenAI or Groq SDK's chat completions interface, asks for a JSON object, includes the schema and extraction rules in the prompt, then calls `ExtractionResult.model_validate_json()`.
4. **Gate relevance and handle failures** in `app.py`. The model's relevance flags select the exact irrelevant-document message. Parsing, API, and validation errors use the exact processing-failure message without exposing provider exception details or document content.
5. **Compute a score vector** in `resume_matcher/scoring.py`. Skill names are normalized and compared exactly. The required/preferred coverage and experience ratio are deterministic. Active dimensions use base weights of 70/20/10 and are normalized if a category is absent.
6. **Render and export** in `app.py` and `resume_matcher/reports.py`. The dark dashboard presents component coverage and five in-memory download formats.

## Supported formats and limitations

- Documents: `.pdf`, `.docx`, `.odt`, `.txt`, `.md`, `.rtf`, `.html`, `.htm`, `.xml`, `.csv`, `.json`, `.xlsx`, `.pptx`.
- Images with optional OCR: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`.
- Legacy `.doc` and arbitrary binary formats are not parsed. Convert those to DOCX/PDF first. A scanned PDF may contain no extractable text; OCR it before upload.
- The model may still omit or misclassify information. Review the evidence and requirements before relying on a score. This is a candidate-facing comparison aid, not a hiring decision system.
- The configured 20 MB upload limit, 100-page PDF limit, 45,000 extracted-character limit, and 20,000-character job-description limit are intentional for small free-tier deployments.

## Project layout

```text
app.py                       Streamlit UI, workflow, and error messages
resume_matcher/models.py     Strict Pydantic extraction schema
resume_matcher/extractors.py In-memory parsers for supported formats
resume_matcher/llm.py        OpenAI/Groq JSON mode and validation
resume_matcher/scoring.py    Deterministic matching vector
resume_matcher/reports.py    JSON, CSV, XLSX, PDF, and Markdown exporters
requirements.txt             Python dependencies
```

