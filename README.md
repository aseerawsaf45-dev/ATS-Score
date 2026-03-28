# 🎯 ATS Resume Scanner

A production-ready Applicant Tracking System (ATS) resume analysis tool. Analyze any resume against a job description with semantic NLP matching, gap analysis, and actionable recruiter-grade suggestions.

---

## 📁 Project Structure

```
ats_scanner/
├── parser.py        # Resume parser (PDF, DOCX, plain text)
├── analyzer.py      # JD parser + NLP matching engine
├── scorer.py        # Weighted scoring system (0–100)
├── suggestions.py   # Actionable suggestion engine
├── main.py          # CLI orchestrator + demo runner
├── app.py           # Streamlit web UI (bonus)
├── requirements.txt # Dependencies
└── README.md
```

---

## ⚙️ Installation

### 1. Clone or download the project

```bash
cd ats_scanner
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows
```

### 3. Install dependencies

**Full install (recommended — includes semantic matching):**
```bash
pip install -r requirements.txt
```

**Minimal install (no semantic matching, uses TF-IDF fallback):**
```bash
pip install pdfplumber python-docx scikit-learn numpy
```

**First run note:** `sentence-transformers` will download the `all-MiniLM-L6-v2` model (~80MB) automatically on first use.

---

## 🚀 Usage

### CLI — Quick Demo

```bash
python main.py --demo
```

### CLI — Analyze Your Resume

```bash
# With PDF resume and JD text file
python main.py --resume resume.pdf --jd job_description.txt

# With DOCX resume
python main.py --resume resume.docx --jd job_description.txt

# Inline JD text
python main.py --resume resume.pdf --jd-text "We need a Python developer with 5 years experience..."

# Output as JSON
python main.py --resume resume.pdf --jd jd.txt --json

# Save JSON report to file
python main.py --resume resume.pdf --jd jd.txt --output report.json

# Disable colors (for CI/logs)
python main.py --demo --no-color
```

### Streamlit Web App

```bash
pip install streamlit
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 📊 Scoring System

| Category              | Weight | Description                            |
|-----------------------|--------|----------------------------------------|
| Skills Match          | 40%    | Matched vs. JD required keywords       |
| Experience Relevance  | 30%    | Years + role depth vs. JD requirements |
| Keyword Density       | 20%    | Keyword coverage + semantic similarity |
| Formatting/Readability| 10%    | Structure, sections, contact info       |
| Semantic Bonus        | +5     | High embedding similarity boost        |
| Penalties             | −15    | Keyword stuffing, weak bullet points   |

---

## 📤 Output Format

```json
{
  "match_score": 72,
  "score_label": "Good Match",
  "percentile": "Top 25% of applicants",
  "score_breakdown": {
    "skills_match": "24/40",
    "experience": "22/30",
    "keyword_density": "14/20",
    "formatting": "9/10",
    "semantic_bonus": "+3.5",
    "penalties": "-0.5"
  },
  "candidate": {
    "name": "Jane Doe",
    "email": "jane@email.com",
    ...
  },
  "matched_skills": ["Python", "React", "REST API", ...],
  "missing_skills": ["Docker", "Kubernetes", "PostgreSQL", ...],
  "partial_matches": [{"jd_keyword": "ML", "resume_skill": "Machine Learning"}],
  "overused_keywords": [],
  "gaps": [
    {
      "type": "skill",
      "item": "Docker",
      "priority": "required",
      "reason": "'Docker' is explicitly listed as a required skill in the JD."
    }
  ],
  "weak_bullets": ["Responsible for building web apps..."],
  "suggestions": {
    "priority_actions": ["🔴 Add 'Docker' to your Skills section..."],
    "skills_to_add": ["[CRITICAL] Add 'Docker'..."],
    "bullet_improvements": [...],
    "keyword_suggestions": [...],
    "structural_tips": [...],
    "experience_tips": [...]
  },
  "improvement_tips": [...]
}
```

---

## 🧠 NLP Stack

| Backend               | Used For                          | Fallback |
|-----------------------|-----------------------------------|---------|
| sentence-transformers | Semantic embedding similarity     | ✓ Yes   |
| scikit-learn TF-IDF   | Keyword similarity fallback       | ✓ Yes   |
| Manual cosine         | Zero-dependency final fallback    | Built-in|
| spaCy (optional)      | Advanced entity recognition       | Optional|

The system degrades gracefully — all features work even without `sentence-transformers`.

---

## 🔬 Advanced Features

- **Semantic matching** — understands "ML" = "Machine Learning", context similarity
- **Synonym detection** — 30+ tech skill alias mappings (e.g., k8s = Kubernetes)
- **Keyword stuffing detection** — penalizes skills mentioned 5+ times
- **Weak bullet detection** — flags "responsible for", "helped to", "worked on", etc.
- **Priority gap analysis** — distinguishes required vs. preferred vs. general skills
- **Experience gap estimation** — compares resume years vs. JD requirements

---

## 📋 Requirements

- Python 3.10+
- See `requirements.txt` for package versions

---

## 🤝 Programmatic Usage

```python
from main import ATSScanner

scanner = ATSScanner()

result = scanner.scan(
    resume_source="path/to/resume.pdf",  # or raw text string
    jd_source="Full job description text...",
)

print(f"Score: {result['match_score']}/100")
print(f"Missing skills: {result['missing_skills']}")
print(f"Priority actions: {result['suggestions']['priority_actions']}")
```
