"""
suggestions.py — Actionable suggestion engine for ATS resume optimization.
Generates recruiter-grade, context-aware improvement tips.
"""

from dataclasses import dataclass, field
from analyzer import MatchResult, ParsedJD
from parser import ParsedResume
from scorer import ScoreBreakdown


@dataclass
class SuggestionReport:
    """Complete set of suggestions for resume improvement."""
    skills_to_add: list[str] = field(default_factory=list)
    bullet_improvements: list[dict] = field(default_factory=list)
    optimization_tips: list[str] = field(default_factory=list)
    keyword_suggestions: list[str] = field(default_factory=list)
    structural_tips: list[str] = field(default_factory=list)
    experience_tips: list[str] = field(default_factory=list)
    priority_actions: list[str] = field(default_factory=list)


# ─── Weak bullet rewrite templates ──────────────────────────────────────────
WEAK_BULLET_REWRITES = {
    "responsible for": "Led / Designed / Built / Managed",
    "helped to": "Contributed to / Collaborated on / Assisted in delivering",
    "worked on": "Developed / Implemented / Engineered",
    "assisted in": "Supported / Contributed to",
    "assisted with": "Partnered on / Facilitated",
    "duties included": "Delivered / Executed / Managed",
    "involved in": "Played a key role in / Contributed to",
    "participated in": "Actively contributed to / Drove",
    "tasked with": "Owned / Led / Delivered",
}

BULLET_TIPS = [
    "Start with a strong action verb (Led, Built, Designed, Optimized, Reduced, Increased).",
    "Quantify your impact: use numbers, percentages, or time savings wherever possible.",
    "Follow the formula: Action + Context + Result (e.g., 'Reduced API latency by 40% by implementing Redis caching').",
    "Avoid vague openings like 'Responsible for' or 'Worked on' — they hide your actual contribution.",
]


class SuggestionEngine:
    """
    Generates prioritized, actionable suggestions for resume improvement
    based on match results, gaps, and resume quality signals.
    """

    def generate(
        self,
        resume: ParsedResume,
        jd: ParsedJD,
        match: MatchResult,
        score: ScoreBreakdown,
    ) -> SuggestionReport:
        report = SuggestionReport()

        report.skills_to_add = self._suggest_skills(match, jd)
        report.bullet_improvements = self._suggest_bullet_rewrites(match, resume)
        report.keyword_suggestions = self._suggest_keywords(match, jd)
        report.structural_tips = self._suggest_structural_improvements(resume, score)
        report.experience_tips = self._suggest_experience_improvements(match, resume, jd)
        report.optimization_tips = self._general_optimization_tips(resume, match, score, jd)
        report.priority_actions = self._prioritize_actions(report, score)

        return report

    # ─────────────────────────────────────────────
    # Suggestion generators
    # ─────────────────────────────────────────────

    def _suggest_skills(self, match: MatchResult, jd: ParsedJD) -> list[str]:
        """Recommend skills to add, prioritized by JD importance."""
        suggestions = []
        required_norms = {s.lower() for s in jd.required_skills}

        for gap in match.skill_gaps[:10]:
            skill = gap["skill"]
            priority = gap["priority"]

            if priority == "required":
                suggestions.append(
                    f"[CRITICAL] Add '{skill}' to your Skills section — it is explicitly "
                    f"required in the JD and its absence may trigger automatic ATS rejection."
                )
            elif priority == "preferred":
                suggestions.append(
                    f"[HIGH] Consider adding '{skill}' to your Skills section. "
                    f"It's listed as preferred and will differentiate you from other candidates."
                )
            else:
                suggestions.append(
                    f"[MEDIUM] '{skill}' appears in the JD's tech stack. "
                    f"If you have experience with it, add it to strengthen keyword matching."
                )

        return suggestions

    def _suggest_bullet_rewrites(
        self, match: MatchResult, resume: ParsedResume
    ) -> list[dict]:
        """Provide rewrite suggestions for weak bullet points."""
        suggestions = []
        seen: set[str] = set()

        for bullet in match.weak_bullets[:8]:
            if bullet in seen:
                continue
            seen.add(bullet)

            # Find which weak pattern triggered this
            detected_prefix = None
            bullet_lower = bullet.lower()
            for prefix, replacement in WEAK_BULLET_REWRITES.items():
                if bullet_lower.startswith(prefix):
                    detected_prefix = prefix
                    break

            if detected_prefix:
                verb_options = WEAK_BULLET_REWRITES[detected_prefix]
                suggestions.append({
                    "original": bullet[:120],
                    "issue": f"Weak opener: '{detected_prefix}' hides your actual contribution.",
                    "suggestion": (
                        f"Replace '{detected_prefix}' with a strong action verb: {verb_options}. "
                        f"Then add a quantifiable result."
                    ),
                    "example": self._generate_rewrite_example(bullet, detected_prefix),
                })
            else:
                suggestions.append({
                    "original": bullet[:120],
                    "issue": "Weak bullet point detected — lacks impact or specificity.",
                    "suggestion": "Rewrite with: Strong Action Verb + Specific Context + Measurable Result.",
                    "example": "e.g., 'Optimized database queries, reducing page load time by 35%'",
                })

        return suggestions

    def _generate_rewrite_example(self, bullet: str, prefix: str) -> str:
        """Generate a generic rewrite example based on the bullet content."""
        # Try to preserve the core topic of the bullet
        core = bullet[len(prefix):].strip().rstrip(".")
        if len(core) > 5:
            return f"e.g., 'Led {core}, resulting in [quantified outcome]'"
        return "e.g., 'Built [system/feature], reducing [metric] by [X]%'"

    def _suggest_keywords(self, match: MatchResult, jd: ParsedJD) -> list[str]:
        """Suggest where and how to incorporate missing keywords."""
        suggestions = []
        keyword_gaps = match.keyword_gaps[:8]

        for kw in keyword_gaps:
            # Context-specific advice
            is_tool = any(
                kw.lower() in cat for cat in [
                    "docker kubernetes git jenkins aws gcp azure",
                    "pytest jest mocha selenium",
                ]
            )
            if is_tool:
                suggestions.append(
                    f"Weave '{kw}' into relevant experience bullet points with context "
                    f"(e.g., 'Deployed service using {kw} on production cluster')."
                )
            else:
                suggestions.append(
                    f"Incorporate '{kw}' naturally into your summary, skills section, "
                    f"or relevant bullet points to improve ATS keyword matching."
                )

        if match.overused_keywords:
            for kw in match.overused_keywords:
                suggestions.append(
                    f"⚠ '{kw}' appears excessively in your resume. "
                    f"ATS systems penalize keyword stuffing — use synonyms and vary phrasing."
                )

        return suggestions

    def _suggest_structural_improvements(
        self, resume: ParsedResume, score: ScoreBreakdown
    ) -> list[str]:
        tips = []

        if not resume.summary:
            tips.append(
                "Add a Professional Summary (3–5 lines) at the top of your resume. "
                "Tailor it to mirror the JD's language — this is the first thing ATS and recruiters read."
            )

        if not resume.linkedin:
            tips.append(
                "Add your LinkedIn profile URL. Many ATS systems and recruiters actively check LinkedIn "
                "for additional context. Format: linkedin.com/in/yourname"
            )

        if not resume.github and any(
            kw in resume.raw_text.lower() for kw in ["software", "developer", "engineer", "code"]
        ):
            tips.append(
                "Add your GitHub profile URL. For technical roles, GitHub is often checked by recruiters "
                "to verify coding ability and open-source contributions."
            )

        if not resume.certifications:
            tips.append(
                "Consider adding a Certifications section. Relevant certifications "
                "(AWS, GCP, PMP, etc.) significantly boost ATS score for many JDs."
            )

        if len(resume.experience) < 2:
            tips.append(
                "Your experience section appears sparse. Expand bullet points with detailed "
                "accomplishments, tools used, and quantifiable outcomes for each role."
            )

        if score.formatting_score < 6:
            tips.append(
                "Improve resume formatting: use consistent date formats, clear section headers, "
                "and bullet points for every experience entry. Avoid tables and text boxes "
                "as they confuse ATS parsers."
            )

        tips.append(
            "Use a single-column layout with standard fonts (Arial, Calibri, Georgia). "
            "Multi-column resumes and graphics are frequently misread by ATS systems."
        )

        return tips

    def _suggest_experience_improvements(
        self, match: MatchResult, resume: ParsedResume, jd: ParsedJD
    ) -> list[str]:
        tips = []

        if match.experience_gap:
            gap = match.experience_gap
            tips.append(
                f"Experience gap detected: JD requires {gap['required_years']:.0f}+ years; "
                f"your resume reflects ~{gap['estimated_years']:.1f} years. "
                f"Compensate by: (1) highlighting complexity of projects, "
                f"(2) adding contract/freelance/open-source work, "
                f"(3) emphasizing leadership and ownership in bullet points."
            )

        if match.weak_bullets:
            tips.append(
                f"Found {len(match.weak_bullets)} weak bullet point(s) in your experience section. "
                f"Rewrite these using strong action verbs + quantified results. "
                f"Hiring managers spend ~7 seconds on first scan — make every bullet count."
            )

        tips.append(
            "For each experience role, ensure you list: (1) company, title, dates, "
            "(2) 3–5 achievement-oriented bullets, (3) specific technologies used. "
            "Thin roles with 1–2 bullets are red flags for experienced roles."
        )

        tips.append(
            "Quantify wherever possible: 'Improved performance by 40%', "
            "'Reduced deployment time from 2 hours to 15 minutes', "
            "'Managed a team of 5 engineers'. Numbers dramatically increase recruiter engagement."
        )

        return tips

    def _general_optimization_tips(
        self, resume: ParsedResume, match: MatchResult, score: ScoreBreakdown, jd: ParsedJD
    ) -> list[str]:
        tips = []

        if score.total < 50:
            tips.append(
                "Your resume is at HIGH RISK of ATS auto-rejection. Prioritize adding "
                "the missing required skills and rewriting weak bullet points before applying."
            )
        elif score.total < 70:
            tips.append(
                "Your resume will likely pass initial ATS screening but may not rank highly. "
                "Focus on skill gap closure and quantifying accomplishments."
            )
        else:
            tips.append(
                "Your resume is competitive. Fine-tune your Professional Summary "
                "to mirror exact language from the JD for maximum ATS score."
            )

        tips.append(
            "Tailor this resume specifically for each application. Generic resumes score "
            "15–25% lower in ATS than tailored ones. Use the JD's exact phrasing."
        )

        tips.append(
            "Save your resume as a PDF (unless DOCX is specifically requested). "
            "PDFs preserve formatting and are reliably parsed by modern ATS systems."
        )

        tips.append(
            "Avoid headers/footers for contact information — ATS often cannot parse "
            "information in headers. Place name, email, and phone in the body."
        )

        return tips

    def _prioritize_actions(
        self, report: SuggestionReport, score: ScoreBreakdown
    ) -> list[str]:
        """Top 5 highest-impact actions, ordered by priority."""
        actions = []

        # Critical skills always first
        critical = [s for s in report.skills_to_add if s.startswith("[CRITICAL]")]
        for c in critical[:2]:
            actions.append(c.replace("[CRITICAL] ", "🔴 "))

        # Weak bullets second
        if report.bullet_improvements:
            actions.append(
                f"🟠 Rewrite {len(report.bullet_improvements)} weak bullet point(s) "
                f"using strong action verbs and quantified outcomes."
            )

        # Missing summary
        summary_tip = next(
            (t for t in report.structural_tips if "Summary" in t), None
        )
        if summary_tip:
            actions.append("🟡 Add a tailored Professional Summary to the top of your resume.")

        # High-priority skills
        high = [s for s in report.skills_to_add if s.startswith("[HIGH]")]
        for h in high[:2]:
            actions.append(h.replace("[HIGH] ", "🟡 "))

        # Experience gap
        if report.experience_tips and any("gap" in t.lower() for t in report.experience_tips):
            actions.append(
                "🔵 Address experience gap by expanding project descriptions and "
                "including freelance/open-source work."
            )

        return actions[:7]  # Return top 7 priority actions
