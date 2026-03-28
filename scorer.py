"""
scorer.py — Weighted scoring system for ATS resume evaluation.

Scoring breakdown:
  Skills match       40%
  Experience         30%
  Keyword density    20%
  Formatting/quality 10%
"""

import re
from dataclasses import dataclass
from analyzer import MatchResult, ParsedJD
from parser import ParsedResume


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown with per-category scores."""
    total: int = 0
    skills_score: float = 0.0       # 0–40
    experience_score: float = 0.0   # 0–30
    keyword_score: float = 0.0      # 0–20
    formatting_score: float = 0.0   # 0–10
    semantic_bonus: float = 0.0     # small boost from semantic similarity
    penalty: float = 0.0            # deductions (stuffing, weak bullets)
    label: str = ""                 # "Excellent" / "Good" / "Fair" / "Poor"
    percentile_estimate: str = ""


class Scorer:
    """
    Computes a weighted ATS compatibility score (0–100).
    """

    # Formatting quality signals
    GOOD_FORMAT_SIGNALS = [
        r"(?i)(phone|email|linkedin|github)",   # contact info present
        r"•|\-|\*",                              # bullet points
        r"(?i)(summary|objective|profile)",      # summary section
        r"(20|19)\d{2}",                         # years (dates present)
    ]

    POOR_FORMAT_SIGNALS = [
        r"(?i)(dear\s+hiring|to\s+whom\s+it\s+may)",  # cover letter mixed in
        r"(.)\1{5,}",                                   # repeated chars (===, ---)
    ]

    def score(
        self,
        resume: ParsedResume,
        jd: ParsedJD,
        match: MatchResult,
    ) -> ScoreBreakdown:
        sb = ScoreBreakdown()

        sb.skills_score = self._score_skills(match, jd)
        sb.experience_score = self._score_experience(resume, jd, match)
        sb.keyword_score = self._score_keywords(match)
        sb.formatting_score = self._score_formatting(resume)
        sb.semantic_bonus = self._semantic_bonus(match.semantic_score)
        sb.penalty = self._compute_penalties(match)

        raw = (
            sb.skills_score
            + sb.experience_score
            + sb.keyword_score
            + sb.formatting_score
            + sb.semantic_bonus
            - sb.penalty
        )
        sb.total = max(0, min(100, round(raw)))
        sb.label = self._label(sb.total)
        sb.percentile_estimate = self._percentile(sb.total)
        return sb

    # ─────────────────────────────────────────────
    # Per-category scorers
    # ─────────────────────────────────────────────

    def _score_skills(self, match: MatchResult, jd: ParsedJD) -> float:
        """40-point bucket: ratio of matched JD skills."""
        total_jd = len(jd.all_keywords)
        if total_jd == 0:
            return 20.0  # neutral if JD has no keywords
        matched_count = len(match.matched_skills)
        ratio = matched_count / total_jd
        return round(ratio * 40, 2)

    def _score_experience(
        self, resume: ParsedResume, jd: ParsedJD, match: MatchResult
    ) -> float:
        """30-point bucket: experience adequacy."""
        base = 30.0

        # Deduct if experience gap exists
        if match.experience_gap:
            gap = match.experience_gap["gap_years"]
            penalty = min(gap * 5, 20)  # up to -20 points
            base -= penalty

        # Boost for multiple roles / projects
        role_count = len(resume.experience)
        if role_count >= 3:
            base = min(base + 5, 30)
        elif role_count == 0:
            base = max(base - 15, 0)

        return round(max(0.0, base), 2)

    def _score_keywords(self, match: MatchResult) -> float:
        """20-point bucket: keyword presence ratio + semantic similarity."""
        kw_ratio = match.keyword_score   # 0–1
        sem_ratio = match.semantic_score  # 0–1
        combined = (kw_ratio * 0.6 + sem_ratio * 0.4)
        return round(combined * 20, 2)

    def _score_formatting(self, resume: ParsedResume) -> float:
        """10-point bucket: structure and readability signals."""
        score = 0.0
        text = resume.raw_text

        # +2 per good signal found
        for pattern in self.GOOD_FORMAT_SIGNALS:
            if re.search(pattern, text):
                score += 2.0

        # -1 per poor signal
        for pattern in self.POOR_FORMAT_SIGNALS:
            if re.search(pattern, text):
                score -= 1.0

        # Bonus for having key sections
        if resume.summary:
            score += 1.0
        if resume.skills:
            score += 1.0

        return round(max(0.0, min(10.0, score)), 2)

    def _semantic_bonus(self, semantic_score: float) -> float:
        """Up to +5 bonus for high semantic similarity."""
        return round(min(5.0, semantic_score * 5), 2)

    def _compute_penalties(self, match: MatchResult) -> float:
        """Deductions for quality issues."""
        penalty = 0.0

        # Keyword stuffing: -2 per stuffed keyword
        penalty += len(match.overused_keywords) * 2

        # Weak bullet points: -1 per weak bullet
        penalty += len(match.weak_bullets) * 1

        return round(min(penalty, 15.0), 2)  # cap at -15

    # ─────────────────────────────────────────────
    # Labels
    # ─────────────────────────────────────────────

    def _label(self, score: int) -> str:
        if score >= 85:
            return "Excellent Match"
        elif score >= 70:
            return "Good Match"
        elif score >= 50:
            return "Fair Match"
        elif score >= 30:
            return "Weak Match"
        return "Poor Match"

    def _percentile(self, score: int) -> str:
        if score >= 85:
            return "Top 10% of applicants"
        elif score >= 70:
            return "Top 25% of applicants"
        elif score >= 50:
            return "Average applicant"
        elif score >= 30:
            return "Below average"
        return "Likely filtered by ATS"
