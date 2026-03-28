"""
analyzer.py — Job Description analysis and NLP-powered matching engine.
Implements semantic similarity, synonym detection, and gap analysis.
"""

import re
import math
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter

from parser import ParsedResume

# ─── Optional NLP backends (graceful degradation) ───────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

try:
    import spacy
    _SPACY_MODEL = None  # lazy-loaded
    _SPACY_AVAILABLE = True
except ImportError:
    _SPACY_AVAILABLE = False


@dataclass
class ParsedJD:
    """Structured representation of a parsed job description."""
    raw_text: str = ""
    title: str = ""
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    experience_required: float = 0.0
    education_required: str = ""
    all_keywords: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """Detailed result of resume-vs-JD matching."""
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    partial_matches: list[dict] = field(default_factory=list)
    overused_keywords: list[str] = field(default_factory=list)
    skill_gaps: list[dict] = field(default_factory=list)
    experience_gap: Optional[dict] = None
    keyword_gaps: list[str] = field(default_factory=list)
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    weak_bullets: list[str] = field(default_factory=list)


# ─── Synonym / alias dictionary ─────────────────────────────────────────────
SKILL_SYNONYMS: dict[str, list[str]] = {
    "machine learning": ["ml", "machine-learning", "statistical learning"],
    "artificial intelligence": ["ai", "artificial-intelligence"],
    "natural language processing": ["nlp", "text mining", "text analytics"],
    "deep learning": ["dl", "neural networks", "ann", "cnn", "rnn", "lstm", "transformer"],
    "python": ["py", "python3", "python 3"],
    "javascript": ["js", "ecmascript", "es6", "es2015"],
    "typescript": ["ts"],
    "react": ["reactjs", "react.js"],
    "node.js": ["nodejs", "node", "express.js", "expressjs"],
    "postgresql": ["postgres", "psql"],
    "mongodb": ["mongo"],
    "kubernetes": ["k8s"],
    "docker": ["containerization", "containers"],
    "continuous integration": ["ci", "ci/cd", "cicd", "continuous deployment"],
    "amazon web services": ["aws", "amazon aws"],
    "google cloud platform": ["gcp", "google cloud"],
    "microsoft azure": ["azure"],
    "restful api": ["rest api", "rest", "restful", "api design", "web api"],
    "graphql": ["graph ql"],
    "sql": ["structured query language", "mysql", "mariadb"],
    "data science": ["data analytics", "data analysis"],
    "version control": ["git", "github", "gitlab", "bitbucket"],
    "agile": ["scrum", "kanban", "sprint", "agile methodology"],
    "object-oriented programming": ["oop", "object oriented"],
    "microservices": ["micro-services", "service-oriented architecture", "soa"],
    "linux": ["unix", "bash", "shell scripting"],
    "computer vision": ["cv", "image processing", "image recognition"],
    "data visualization": ["tableau", "power bi", "matplotlib", "seaborn", "plotly"],
    "big data": ["hadoop", "spark", "apache spark", "hive", "kafka"],
    "cybersecurity": ["information security", "infosec", "security engineering"],
    "ui/ux": ["user interface", "user experience", "ux design", "ui design"],
}

# Build reverse lookup: alias → canonical
ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in SKILL_SYNONYMS.items():
    ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias.lower()] = canonical


def normalize_skill(skill: str) -> str:
    """Normalize a skill string to its canonical form."""
    return ALIAS_TO_CANONICAL.get(skill.strip().lower(), skill.strip().lower())


# ─── Keyword stuffing detection ─────────────────────────────────────────────
def detect_keyword_stuffing(text: str, skills: list[str], threshold: int = 5) -> list[str]:
    """Flag skills mentioned more than `threshold` times (possible stuffing)."""
    text_lower = text.lower()
    stuffed = []
    for skill in skills:
        count = len(re.findall(rf"\b{re.escape(skill.lower())}\b", text_lower))
        if count >= threshold:
            stuffed.append(skill)
    return stuffed


class JDParser:
    """Parses raw job description text into structured data."""

    MUST_HAVE_SIGNALS = r"(?i)(required|must\s+have|essential|mandatory|minimum|at\s+least)"
    NICE_TO_HAVE_SIGNALS = r"(?i)(preferred|nice\s+to\s+have|bonus|plus|desired|advantageous)"
    EXPERIENCE_PATTERN = re.compile(
        r"(\d+)\+?\s*(?:to\s*\d+\s*)?years?\s+(?:of\s+)?(?:professional\s+)?experience", re.I
    )

    # Common tech keywords to extract from JD text
    TECH_KEYWORD_RE = re.compile(
        r"\b("
        r"python|java(?:script)?|typescript|c\+\+|golang|rust|ruby|php|swift|kotlin|scala|r\b|"
        r"react|angular|vue|svelte|next\.?js|nuxt|django|flask|fastapi|spring|laravel|rails|"
        r"node\.?js|express|graphql|rest\b|grpc|"
        r"sql|mysql|postgres(?:ql)?|mongodb|redis|cassandra|dynamodb|"
        r"aws|gcp|azure|heroku|vercel|netlify|"
        r"docker|kubernetes|k8s|terraform|ansible|jenkins|github\s*actions|circleci|"
        r"machine\s*learning|deep\s*learning|nlp|llm|pytorch|tensorflow|keras|scikit[- ]learn|"
        r"pandas|numpy|spark|hadoop|kafka|airflow|"
        r"git|linux|bash|shell|ci/?cd|agile|scrum|devops|microservices|"
        r"html|css|sass|webpack|vite|tailwind"
        r")\b",
        re.I,
    )

    def parse(self, jd_text: str) -> ParsedJD:
        jd = ParsedJD(raw_text=jd_text)
        jd.title = self._extract_title(jd_text)
        jd.required_skills = self._extract_required_skills(jd_text)
        jd.preferred_skills = self._extract_preferred_skills(jd_text)
        jd.responsibilities = self._extract_responsibilities(jd_text)
        jd.keywords = self._extract_tech_keywords(jd_text)
        jd.experience_required = self._extract_experience_requirement(jd_text)
        jd.education_required = self._extract_education_requirement(jd_text)
        jd.all_keywords = list(set(jd.required_skills + jd.preferred_skills + jd.keywords))
        return jd

    def _extract_title(self, text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line and len(line) < 80:
                return line
        return ""

    def _extract_tech_keywords(self, text: str) -> list[str]:
        matches = self.TECH_KEYWORD_RE.findall(text)
        seen: set[str] = set()
        result = []
        for m in matches:
            norm = normalize_skill(m)
            if norm not in seen:
                seen.add(norm)
                result.append(m.strip())
        return result

    def _extract_required_skills(self, text: str) -> list[str]:
        return self._extract_skills_from_section(text, self.MUST_HAVE_SIGNALS)

    def _extract_preferred_skills(self, text: str) -> list[str]:
        return self._extract_skills_from_section(text, self.NICE_TO_HAVE_SIGNALS)

    def _extract_skills_from_section(self, text: str, signal_pattern: str) -> list[str]:
        """Extract tech skills near must-have / nice-to-have signal words."""
        skills = []
        lines = text.splitlines()
        in_signal_zone = False
        for line in lines:
            if re.search(signal_pattern, line):
                in_signal_zone = True
            if in_signal_zone:
                found = self.TECH_KEYWORD_RE.findall(line)
                skills.extend([s.strip() for s in found])
            # Reset after a blank line
            if not line.strip():
                in_signal_zone = False
        # Deduplicate preserving order
        seen: set[str] = set()
        result = []
        for s in skills:
            ns = normalize_skill(s)
            if ns not in seen:
                seen.add(ns)
                result.append(s)
        return result

    def _extract_responsibilities(self, text: str) -> list[str]:
        bullet_re = re.compile(r"^[•·▪▸►\-\*]\s*(.+)")
        responsibilities = []
        for line in text.splitlines():
            m = bullet_re.match(line.strip())
            if m:
                responsibilities.append(m.group(1).strip())
        return responsibilities[:20]  # cap at 20

    def _extract_experience_requirement(self, text: str) -> float:
        match = self.EXPERIENCE_PATTERN.search(text)
        return float(match.group(1)) if match else 0.0

    def _extract_education_requirement(self, text: str) -> str:
        edu_patterns = [
            r"(?i)(Ph\.?D\.?|Doctor(?:ate)?)",
            r"(?i)(Master'?s?|M\.?S\.?|M\.?Tech)",
            r"(?i)(Bachelor'?s?|B\.?S\.?|B\.?E\.?|B\.?Tech)",
        ]
        for pattern in edu_patterns:
            if re.search(pattern, text):
                return re.search(pattern, text).group(0)
        return ""


class MatchingEngine:
    """
    Core matching engine: keyword + semantic similarity + gap analysis.
    Degrades gracefully if sentence-transformers or sklearn are unavailable.
    """

    def __init__(self, semantic_model: str = "all-MiniLM-L6-v2"):
        self._model = None
        self._model_name = semantic_model
        self._load_semantic_model()

    def _load_semantic_model(self):
        if _ST_AVAILABLE:
            try:
                self._model = SentenceTransformer(self._model_name)
            except Exception:
                self._model = None

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    def match(self, resume: ParsedResume, jd: ParsedJD) -> MatchResult:
        result = MatchResult()
        result.matched_skills, result.missing_skills, result.partial_matches = (
            self._match_skills(resume.skills, jd.all_keywords)
        )
        result.keyword_gaps = self._find_keyword_gaps(resume.raw_text, jd.all_keywords)
        result.overused_keywords = detect_keyword_stuffing(resume.raw_text, resume.skills)
        result.skill_gaps = self._build_skill_gaps(result.missing_skills, jd)
        result.experience_gap = self._check_experience_gap(resume, jd)
        result.semantic_score = self._semantic_similarity(resume.raw_text, jd.raw_text)
        result.keyword_score = self._keyword_match_score(
            resume.raw_text, jd.all_keywords, result.matched_skills
        )
        result.weak_bullets = self._collect_weak_bullets(resume)
        return result

    # ─────────────────────────────────────────────
    # Skill matching
    # ─────────────────────────────────────────────

    def _match_skills(
        self, resume_skills: list[str], jd_keywords: list[str]
    ) -> tuple[list[str], list[str], list[dict]]:
        """
        Three-tier matching:
        1. Exact (case-insensitive)
        2. Synonym / alias match
        3. Substring / partial match
        """
        matched: list[str] = []
        missing: list[str] = []
        partial: list[dict] = []

        resume_normalized = {normalize_skill(s): s for s in resume_skills}
        resume_lower = {s.lower(): s for s in resume_skills}

        for kw in jd_keywords:
            kw_norm = normalize_skill(kw)

            # Tier 1: exact normalized match
            if kw_norm in resume_normalized:
                matched.append(kw)
                continue

            # Tier 2: check if resume skill normalizes to same canonical form
            synonym_hit = any(
                normalize_skill(rs) == kw_norm for rs in resume_skills
            )
            if synonym_hit:
                matched.append(kw)
                continue

            # Tier 3: substring check
            kw_lower = kw.lower()
            substr_hit = None
            for rs_lower, rs_orig in resume_lower.items():
                if kw_lower in rs_lower or rs_lower in kw_lower:
                    substr_hit = rs_orig
                    break

            if substr_hit:
                partial.append({"jd_keyword": kw, "resume_skill": substr_hit})
                matched.append(kw)  # count as matched with note
                continue

            missing.append(kw)

        return matched, missing, partial

    def _find_keyword_gaps(self, resume_text: str, jd_keywords: list[str]) -> list[str]:
        """Keywords from JD not mentioned anywhere in resume text."""
        text_lower = resume_text.lower()
        gaps = []
        for kw in jd_keywords:
            kw_lower = kw.lower()
            if kw_lower not in text_lower and normalize_skill(kw) not in text_lower:
                gaps.append(kw)
        return gaps

    def _build_skill_gaps(self, missing_skills: list[str], jd: ParsedJD) -> list[dict]:
        """Attach reasoning to each missing skill."""
        gaps = []
        required_set = {normalize_skill(s) for s in jd.required_skills}
        preferred_set = {normalize_skill(s) for s in jd.preferred_skills}

        for skill in missing_skills:
            skill_norm = normalize_skill(skill)
            priority = "required" if skill_norm in required_set else (
                "preferred" if skill_norm in preferred_set else "general"
            )
            gaps.append({
                "skill": skill,
                "priority": priority,
                "reason": (
                    f"'{skill}' is explicitly listed as a required skill in the JD."
                    if priority == "required"
                    else f"'{skill}' is a preferred/bonus skill that would strengthen your application."
                    if priority == "preferred"
                    else f"'{skill}' appears in the JD and is part of the expected tech stack."
                ),
            })
        # Sort: required first
        gaps.sort(key=lambda x: {"required": 0, "preferred": 1, "general": 2}[x["priority"]])
        return gaps

    def _check_experience_gap(self, resume: ParsedResume, jd: ParsedJD) -> Optional[dict]:
        if jd.experience_required == 0:
            return None
        delta = jd.experience_required - resume.total_years_experience
        if delta > 0:
            return {
                "required_years": jd.experience_required,
                "estimated_years": resume.total_years_experience,
                "gap_years": delta,
                "severity": "high" if delta >= 2 else "medium",
                "reason": (
                    f"JD requires {jd.experience_required:.0f}+ years of experience. "
                    f"Your resume indicates approximately {resume.total_years_experience:.1f} years."
                ),
            }
        return None

    # ─────────────────────────────────────────────
    # Scoring helpers
    # ─────────────────────────────────────────────

    def _semantic_similarity(self, text_a: str, text_b: str) -> float:
        """Compute semantic similarity using sentence-transformers or TF-IDF fallback."""
        if self._model is not None:
            try:
                emb = self._model.encode([text_a[:512], text_b[:512]])
                sim = float(np.dot(emb[0], emb[1]) / (
                    np.linalg.norm(emb[0]) * np.linalg.norm(emb[1]) + 1e-8
                ))
                return max(0.0, min(1.0, sim))
            except Exception:
                pass

        if _SKLEARN_AVAILABLE:
            try:
                vec = TfidfVectorizer(stop_words="english", max_features=5000)
                matrix = vec.fit_transform([text_a, text_b])
                sim = float(sk_cosine(matrix[0], matrix[1])[0][0])
                return max(0.0, min(1.0, sim))
            except Exception:
                pass

        # Manual cosine similarity on word overlap
        return self._manual_cosine(text_a, text_b)

    def _manual_cosine(self, text_a: str, text_b: str) -> float:
        stop = {"the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at", "by"}
        tokens_a = Counter(w for w in re.findall(r"\w+", text_a.lower()) if w not in stop)
        tokens_b = Counter(w for w in re.findall(r"\w+", text_b.lower()) if w not in stop)
        vocab = set(tokens_a) | set(tokens_b)
        if not vocab:
            return 0.0
        dot = sum(tokens_a[w] * tokens_b[w] for w in vocab)
        mag_a = math.sqrt(sum(v ** 2 for v in tokens_a.values()))
        mag_b = math.sqrt(sum(v ** 2 for v in tokens_b.values()))
        return dot / (mag_a * mag_b + 1e-8)

    def _keyword_match_score(
        self, resume_text: str, jd_keywords: list[str], matched: list[str]
    ) -> float:
        if not jd_keywords:
            return 0.0
        return len(matched) / len(jd_keywords)

    def _collect_weak_bullets(self, resume: ParsedResume) -> list[str]:
        weak = []
        for exp in resume.experience:
            weak.extend(exp.get("weak_bullets", []))
        return weak
