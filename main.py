"""
main.py — ATS Resume Scanner: main orchestrator.

Usage:
    python main.py --resume path/to/resume.pdf --jd path/to/jd.txt
    python main.py --resume path/to/resume.pdf --jd path/to/jd.txt --json
    python main.py --resume path/to/resume.docx --jd-text "Job description text..."
    python main.py --demo   # Run with built-in example data
"""

import argparse
import os
import json
import sys
import textwrap
from pathlib import Path
from dataclasses import asdict

from parser import ResumeParser
from analyzer import JDParser, MatchingEngine
from scorer import Scorer
from suggestions import SuggestionEngine


# ─── ANSI color codes ────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    GRAY   = "\033[90m"
    WHITE  = "\033[97m"


def colorize(text: str, *codes: str) -> str:
    return "".join(codes) + text + C.RESET


# ─── ATSScanner orchestrator ─────────────────────────────────────────────────

class ATSScanner:
    """
    Main orchestrator for the ATS Resume Scanner pipeline:
    Parse → Analyze → Score → Suggest → Report
    """

    def __init__(self):
        self.resume_parser = ResumeParser()
        self.jd_parser = JDParser()
        self.matching_engine = MatchingEngine()
        self.scorer = Scorer()
        self.suggestion_engine = SuggestionEngine()

    def scan(
        self,
        resume_source: str | Path,
        jd_source: str,
        resume_file_type: str | None = None,
    ) -> dict:
        """
        Full pipeline: parse both inputs, match, score, suggest.

        Args:
            resume_source: File path or raw text of the resume.
            jd_source: Raw text of the job description.
            resume_file_type: 'pdf', 'docx', or 'text'. Auto-detected from path.

        Returns:
            Structured result dict (also printable as JSON).
        """
        # 1. Parse
        resume = self.resume_parser.parse(resume_source, resume_file_type)
        jd = self.jd_parser.parse(jd_source)

        # 2. Match
        match = self.matching_engine.match(resume, jd)

        # 3. Score
        score = self.scorer.score(resume, jd, match)

        # 4. Suggest
        suggestions = self.suggestion_engine.generate(resume, jd, match, score)

        # 5. Build output
        result = self._build_result(resume, jd, match, score, suggestions)
        return result

    def _build_result(self, resume, jd, match, score, suggestions) -> dict:
        gaps = []
        for sg in match.skill_gaps:
            gaps.append({
                "type": "skill",
                "item": sg["skill"],
                "priority": sg["priority"],
                "reason": sg["reason"],
            })
        if match.experience_gap:
            gaps.append({
                "type": "experience",
                "item": f"{match.experience_gap['gap_years']:.1f} years",
                "priority": "high",
                "reason": match.experience_gap["reason"],
            })
        for kw in match.keyword_gaps:
            gaps.append({
                "type": "keyword",
                "item": kw,
                "priority": "medium",
                "reason": f"'{kw}' appears in JD but not detected in resume text.",
            })

        return {
            "match_score": score.total,
            "score_label": score.label,
            "percentile": score.percentile_estimate,
            "score_breakdown": {
                "skills_match": f"{score.skills_score}/40",
                "experience": f"{score.experience_score}/30",
                "keyword_density": f"{score.keyword_score}/20",
                "formatting": f"{score.formatting_score}/10",
                "semantic_bonus": f"+{score.semantic_bonus}",
                "penalties": f"-{score.penalty}",
            },
            "candidate": {
                "name": resume.name,
                "email": resume.email,
                "phone": resume.phone,
                "linkedin": resume.linkedin,
                "github": resume.github,
                "estimated_experience_years": resume.total_years_experience,
            },
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
            "partial_matches": match.partial_matches,
            "overused_keywords": match.overused_keywords,
            "gaps": gaps,
            "weak_bullets": match.weak_bullets,
            "suggestions": {
                "priority_actions": suggestions.priority_actions,
                "skills_to_add": suggestions.skills_to_add,
                "bullet_improvements": suggestions.bullet_improvements,
                "keyword_suggestions": suggestions.keyword_suggestions,
                "structural_tips": suggestions.structural_tips,
                "experience_tips": suggestions.experience_tips,
            },
            "improvement_tips": suggestions.optimization_tips,
        }


# ─── CLI Report Printer ───────────────────────────────────────────────────────

def print_report(result: dict):
    """Print a clean, human-readable ATS scan report to stdout."""
    score = result["match_score"]
    label = result["score_label"]
    sep = "═" * 70

    # Determine score color
    if score >= 75:
        score_color = C.GREEN
    elif score >= 50:
        score_color = C.YELLOW
    else:
        score_color = C.RED

    print(f"\n{colorize(sep, C.BOLD, C.CYAN)}")
    print(colorize("  ATS RESUME SCANNER — ANALYSIS REPORT", C.BOLD, C.WHITE))
    print(colorize(sep, C.BOLD, C.CYAN))

    # ── Candidate Info ──────────────────────────────────────────────────
    c = result["candidate"]
    print(f"\n{colorize('CANDIDATE', C.BOLD, C.CYAN)}")
    if c["name"]:
        print(f"  Name     : {c['name']}")
    if c["email"]:
        print(f"  Email    : {c['email']}")
    if c["phone"]:
        print(f"  Phone    : {c['phone']}")
    if c["linkedin"]:
        print(f"  LinkedIn : {c['linkedin']}")
    if c["github"]:
        print(f"  GitHub   : {c['github']}")
    print(f"  Est. Exp : {c['estimated_experience_years']:.1f} years")

    # ── Score ────────────────────────────────────────────────────────────
    print(f"\n{colorize('MATCH SCORE', C.BOLD, C.CYAN)}")
    bar_filled = int(score / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    print(f"  {colorize(f'{score:3d}/100', score_color, C.BOLD)}  [{colorize(bar, score_color)}]  {label}")
    print(f"  Percentile: {result['percentile']}")

    # ── Score Breakdown ──────────────────────────────────────────────────
    bd = result["score_breakdown"]
    print(f"\n{colorize('SCORE BREAKDOWN', C.BOLD, C.CYAN)}")
    print(f"  Skills Match       : {bd['skills_match']}")
    print(f"  Experience         : {bd['experience']}")
    print(f"  Keyword Density    : {bd['keyword_density']}")
    print(f"  Formatting/Quality : {bd['formatting']}")
    print(f"  Semantic Bonus     : {bd['semantic_bonus']}")
    print(f"  Penalties          : {bd['penalties']}")

    # ── Skills ───────────────────────────────────────────────────────────
    matched = result["matched_skills"]
    missing = result["missing_skills"]
    partial = result["partial_matches"]

    print(f"\n{colorize('SKILLS ANALYSIS', C.BOLD, C.CYAN)}")
    if matched:
        print(colorize(f"  ✓ Matched ({len(matched)})", C.GREEN, C.BOLD))
        _print_chips(matched, C.GREEN)
    if missing:
        print(colorize(f"\n  ✗ Missing ({len(missing)})", C.RED, C.BOLD))
        _print_chips(missing, C.RED)
    if partial:
        print(colorize(f"\n  ~ Partial Matches ({len(partial)})", C.YELLOW, C.BOLD))
        for p in partial:
            print(f"    • JD: '{p['jd_keyword']}' ← Resume: '{p['resume_skill']}'")
    if result["overused_keywords"]:
        print(colorize(f"\n  ⚠ Potentially Overused", C.YELLOW, C.BOLD))
        _print_chips(result["overused_keywords"], C.YELLOW)

    # ── Gaps ─────────────────────────────────────────────────────────────
    gaps = result["gaps"]
    if gaps:
        print(f"\n{colorize('GAP ANALYSIS', C.BOLD, C.CYAN)}")
        priority_order = {"high": 0, "required": 0, "preferred": 1, "medium": 2, "general": 3}
        gaps_sorted = sorted(gaps, key=lambda g: priority_order.get(g["priority"], 3))
        for gap in gaps_sorted[:10]:
            icon = {"high": "🔴", "required": "🔴", "preferred": "🟡", "medium": "🟠", "general": "🔵"}.get(
                gap["priority"], "•"
            )
            gtype = gap["type"].capitalize()
            item = gap["item"]
            reason = textwrap.fill(gap["reason"], width=60, subsequent_indent=" " * 10)
            print(f"  {icon} [{gtype}] {colorize(item, C.BOLD)}")
            print(f"         {colorize(reason, C.GRAY)}")

    # ── Weak Bullets ─────────────────────────────────────────────────────
    weak = result["weak_bullets"]
    if weak:
        print(f"\n{colorize('WEAK BULLET POINTS DETECTED', C.BOLD, C.CYAN)}")
        for b in weak[:5]:
            print(f"  {colorize('⚠', C.YELLOW)}  \"{b[:90]}{'...' if len(b) > 90 else ''}\"")

    # ── Priority Actions ─────────────────────────────────────────────────
    actions = result["suggestions"]["priority_actions"]
    if actions:
        print(f"\n{colorize('PRIORITY ACTIONS (DO THESE FIRST)', C.BOLD, C.CYAN)}")
        for i, action in enumerate(actions, 1):
            wrapped = textwrap.fill(action, width=64, subsequent_indent="     ")
            print(f"  {i}. {wrapped}")

    # ── Improvement Tips ─────────────────────────────────────────────────
    tips = result["improvement_tips"]
    if tips:
        print(f"\n{colorize('OPTIMIZATION TIPS', C.BOLD, C.CYAN)}")
        for tip in tips:
            wrapped = textwrap.fill(tip, width=66, subsequent_indent="     ")
            print(f"  ▸ {wrapped}")

    # ── Bullet Improvement Suggestions ───────────────────────────────────
    bi = result["suggestions"]["bullet_improvements"]
    if bi:
        print(f"\n{colorize('BULLET POINT IMPROVEMENTS', C.BOLD, C.CYAN)}")
        for item in bi[:4]:
            print(f"  {colorize('Original:', C.GRAY)}  \"{item['original'][:80]}\"")
            print(f"  {colorize('Issue:', C.RED)}     {item['issue']}")
            print(f"  {colorize('Fix:', C.GREEN)}      {item['suggestion']}")
            print(f"  {colorize('Example:', C.BLUE)}   {item['example']}")
            print()

    # ── Keyword Suggestions ──────────────────────────────────────────────
    kw_suggestions = result["suggestions"]["keyword_suggestions"]
    if kw_suggestions:
        print(f"\n{colorize('KEYWORD OPTIMIZATION', C.BOLD, C.CYAN)}")
        for kw in kw_suggestions[:6]:
            wrapped = textwrap.fill(kw, width=66, subsequent_indent="    ")
            print(f"  ▸ {wrapped}")

    # ── Structural Tips ──────────────────────────────────────────────────
    struct_tips = result["suggestions"]["structural_tips"]
    if struct_tips:
        print(f"\n{colorize('STRUCTURAL IMPROVEMENTS', C.BOLD, C.CYAN)}")
        for tip in struct_tips[:5]:
            wrapped = textwrap.fill(tip, width=66, subsequent_indent="    ")
            print(f"  ▸ {wrapped}")

    print(f"\n{colorize(sep, C.BOLD, C.CYAN)}\n")


def _print_chips(items: list[str], color: str, per_row: int = 5):
    """Print skill chips in rows."""
    for i in range(0, len(items), per_row):
        row = items[i:i + per_row]
        print("    " + "  ".join(colorize(f"[{s}]", color) for s in row))


# ─── Demo data ───────────────────────────────────────────────────────────────

DEMO_RESUME_TEXT = """
Jane Doe
jane.doe@email.com | +1-555-123-4567 | linkedin.com/in/janedoe | github.com/janedoe

SUMMARY
Experienced software developer with 3 years of experience building web applications
using Python and JavaScript.

SKILLS
Python, JavaScript, React, Django, HTML, CSS, Git, MySQL, REST API, Linux

EXPERIENCE

Software Developer — TechCorp Inc.  (2021 – 2024)
• Responsible for building web applications using Django and React
• Worked on database optimization tasks
• Helped to deploy applications to production servers
• Assisted with writing unit tests for the codebase

Junior Developer — WebStart LLC  (2020 – 2021)
• Involved in developing REST APIs using Python Flask
• Participated in code reviews and team meetings
• Worked on fixing bugs in the frontend React components

EDUCATION
Bachelor of Science in Computer Science — State University (2020)

PROJECTS
E-commerce Platform
Built a full-stack e-commerce site using React and Django REST framework.
"""

DEMO_JD_TEXT = """
Senior Software Engineer — FinTech Platform

We are looking for a Senior Software Engineer to join our growing team.

Required Skills:
• 5+ years of professional software engineering experience
• Python (Django, FastAPI)
• TypeScript / JavaScript
• React or Vue.js
• PostgreSQL and Redis
• Docker and Kubernetes
• AWS or GCP
• CI/CD pipelines (GitHub Actions, Jenkins)
• Microservices architecture
• Machine Learning or data pipelines experience

Preferred / Nice to Have:
• GraphQL
• Terraform
• Apache Kafka
• System design experience

Responsibilities:
• Design and implement scalable backend services
• Lead technical architecture discussions
• Mentor junior engineers
• Collaborate with product and data teams
• Participate in on-call rotations
"""


# ─── CLI entrypoint ───────────────────────────────────────────────────────────

def main():
    # Force UTF-8 output on Windows to correctly render box-drawing chars and emoji
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")  # Set Windows console code page to UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="ATS Resume Scanner — Analyze your resume against a job description.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python main.py --demo
          python main.py --resume resume.pdf --jd jd.txt
          python main.py --resume resume.docx --jd jd.txt --json
          python main.py --resume resume.pdf --jd-text "We need a Python developer..."
        """),
    )
    parser.add_argument("--resume", type=str, help="Path to resume file (PDF or DOCX)")
    parser.add_argument("--jd", type=str, help="Path to job description text file")
    parser.add_argument("--jd-text", type=str, help="Job description as inline text")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--output", type=str, help="Save JSON results to this file path")
    parser.add_argument("--demo", action="store_true", help="Run with built-in demo data")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")

    args = parser.parse_args()

    if args.no_color:
        for attr in dir(C):
            if not attr.startswith("_"):
                setattr(C, attr, "")

    scanner = ATSScanner()

    # ── Determine inputs ────────────────────────────────────────────────
    if args.demo:
        print(colorize("\n⚙  Running ATS Scanner with built-in demo data...\n", C.GRAY), file=sys.stderr)
        resume_source = DEMO_RESUME_TEXT
        jd_source = DEMO_JD_TEXT
        resume_file_type = "text"
    else:
        if not args.resume:
            print(colorize("Error: --resume is required (or use --demo)", C.RED))
            sys.exit(1)
        if not args.jd and not args.jd_text:
            print(colorize("Error: --jd or --jd-text is required", C.RED))
            sys.exit(1)

        resume_source = args.resume
        resume_file_type = None  # auto-detect from extension

        if args.jd:
            jd_path = Path(args.jd)
            if not jd_path.exists():
                print(colorize(f"Error: JD file not found: {args.jd}", C.RED))
                sys.exit(1)
            jd_source = jd_path.read_text(encoding="utf-8")
        else:
            jd_source = args.jd_text

    # ── Run scan ────────────────────────────────────────────────────────
    try:
        result = scanner.scan(resume_source, jd_source, resume_file_type)
    except ImportError as e:
        print(colorize(f"\n⚠  Missing dependency: {e}", C.YELLOW))
        print("Run: pip install -r requirements.txt\n")
        sys.exit(1)
    except Exception as e:
        print(colorize(f"\n✗  Scanner error: {e}", C.RED))
        raise

    # ── Output ──────────────────────────────────────────────────────────
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(colorize(f"\n✓  JSON report saved to: {out_path}", C.GREEN))


if __name__ == "__main__":
    main()
