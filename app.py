"""
app.py — Streamlit web UI for the ATS Resume Scanner.

Run: streamlit run app.py
"""

import json
import sys
import io
import tempfile
from pathlib import Path

try:
    import streamlit as st
except ImportError:
    print("Streamlit not installed. Run: pip install streamlit")
    sys.exit(1)

from main import ATSScanner, DEMO_JD_TEXT, DEMO_RESUME_TEXT

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ATS Resume Scanner",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1a1a2e; }
    .score-box {
        text-align: center; padding: 2rem; border-radius: 16px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    .score-number { font-size: 5rem; font-weight: 900; line-height: 1; }
    .score-label  { font-size: 1.2rem; opacity: 0.9; margin-top: 0.5rem; }
    .metric-card {
        background: #f8f9fa; border-radius: 12px; padding: 1rem;
        border-left: 4px solid #667eea; margin-bottom: 0.5rem;
    }
    .skill-chip {
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        margin: 3px; font-size: 0.85rem; font-weight: 600;
    }
    .chip-green  { background: #d4edda; color: #155724; }
    .chip-red    { background: #f8d7da; color: #721c24; }
    .chip-yellow { background: #fff3cd; color: #856404; }
    .gap-card {
        background: #fff; border: 1px solid #dee2e6; border-radius: 10px;
        padding: 0.8rem 1rem; margin-bottom: 0.5rem;
    }
    .priority-high { border-left: 4px solid #dc3545; }
    .priority-med  { border-left: 4px solid #ffc107; }
    .priority-low  { border-left: 4px solid #0d6efd; }
    .action-item {
        background: #f0f4ff; border-radius: 8px; padding: 0.6rem 1rem;
        margin-bottom: 0.4rem; font-size: 0.9rem;
    }
    .weak-bullet {
        background: #fff8e1; border-left: 3px solid #ff9800;
        padding: 0.5rem 0.8rem; border-radius: 4px; margin-bottom: 0.3rem;
        font-size: 0.85rem; color: #555;
    }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎯 ATS Resume Scanner")
    st.markdown("---")
    st.markdown("**How it works:**")
    st.markdown("""
    1. Upload your resume (PDF/DOCX) or paste text
    2. Paste the job description
    3. Click **Analyze**
    4. Get your ATS score + detailed improvement plan
    """)
    st.markdown("---")
    st.markdown("**Score Weights:**")
    st.markdown("- 🎯 Skills Match: **40%**")
    st.markdown("- 💼 Experience: **30%**")
    st.markdown("- 🔑 Keywords: **20%**")
    st.markdown("- 📄 Formatting: **10%**")
    st.markdown("---")
    use_demo = st.button("🚀 Load Demo Data", use_container_width=True)
    if use_demo:
        st.session_state["demo_mode"] = True

# ─── Main content ─────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🎯 ATS Resume Scanner</div>', unsafe_allow_html=True)
st.markdown("*Analyze your resume against any job description and get actionable improvement tips.*")
st.markdown("---")

col1, col2 = st.columns(2, gap="large")

demo_mode = st.session_state.get("demo_mode", False)

with col1:
    st.subheader("📄 Your Resume")
    input_method = st.radio("Input method", ["Upload File", "Paste Text"], horizontal=True)

    resume_source = None
    resume_file_type = None

    if input_method == "Upload File":
        uploaded = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])
        if uploaded:
            resume_source = uploaded.read()
            resume_file_type = uploaded.name.rsplit(".", 1)[-1].lower()
            st.success(f"✓ Loaded: {uploaded.name}")
    else:
        default_resume = DEMO_RESUME_TEXT if demo_mode else ""
        resume_text = st.text_area("Paste resume text here", value=default_resume, height=320)
        if resume_text.strip():
            resume_source = resume_text
            resume_file_type = "text"

with col2:
    st.subheader("📋 Job Description")
    default_jd = DEMO_JD_TEXT if demo_mode else ""
    jd_text = st.text_area("Paste the full job description", value=default_jd, height=360)

st.markdown("---")
analyze_btn = st.button("🔍 Analyze Resume", type="primary", use_container_width=True)

# ─── Analysis ────────────────────────────────────────────────────────────────
if analyze_btn:
    if not resume_source:
        st.error("Please provide your resume (upload file or paste text).")
    elif not jd_text.strip():
        st.error("Please paste a job description.")
    else:
        with st.spinner("Analyzing your resume... (semantic matching may take a moment)"):
            try:
                scanner = ATSScanner()
                result = scanner.scan(resume_source, jd_text, resume_file_type)
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.stop()

        st.markdown("---")
        st.markdown("## 📊 Analysis Results")

        # ── Score + Breakdown ────────────────────────────────────────────
        rc1, rc2, rc3 = st.columns([1, 1, 2])

        with rc1:
            score = result["match_score"]
            color = "#28a745" if score >= 75 else "#ffc107" if score >= 50 else "#dc3545"
            st.markdown(f"""
            <div class="score-box" style="background: linear-gradient(135deg, {color}cc, {color});">
                <div class="score-number">{score}</div>
                <div class="score-label">/100 — {result['score_label']}</div>
                <div style="font-size:0.85rem; opacity:0.8; margin-top:0.5rem;">{result['percentile']}</div>
            </div>
            """, unsafe_allow_html=True)

        with rc2:
            bd = result["score_breakdown"]
            st.markdown("**Score Breakdown**")
            for label, val in [
                ("🎯 Skills", bd["skills_match"]),
                ("💼 Experience", bd["experience"]),
                ("🔑 Keywords", bd["keyword_density"]),
                ("📄 Formatting", bd["formatting"]),
                ("✨ Semantic Bonus", bd["semantic_bonus"]),
                ("⚠ Penalties", bd["penalties"]),
            ]:
                st.markdown(f'<div class="metric-card"><b>{label}</b>: {val}</div>', unsafe_allow_html=True)

        with rc3:
            cand = result["candidate"]
            st.markdown("**Candidate Info**")
            info_items = [
                ("Name", cand["name"]),
                ("Email", cand["email"]),
                ("Phone", cand["phone"]),
                ("LinkedIn", cand["linkedin"]),
                ("GitHub", cand["github"]),
                ("Est. Experience", f"{cand['estimated_experience_years']:.1f} years"),
            ]
            for k, v in info_items:
                if v:
                    st.markdown(f"**{k}:** {v}")

        st.markdown("---")

        # ── Section 1: Skills ────────────────────────────────────────────
        st.markdown("## 🎯 Skills Analysis")
        col_a, col_b = st.columns(2)
        with col_a:
            matched = result["matched_skills"]
            st.markdown(f"### ✅ Matched Skills ({len(matched)})")
            if matched:
                chips = " ".join(
                    f'<span class="skill-chip chip-green">{s}</span>' for s in matched
                )
                st.markdown(chips, unsafe_allow_html=True)
            else:
                st.info("No skills matched.")

            partial = result["partial_matches"]
            if partial:
                st.markdown(f"### 〜 Partial Matches ({len(partial)})")
                for p in partial:
                    st.markdown(
                        f'<span class="skill-chip chip-yellow">{p["jd_keyword"]}</span> '
                        f'← *{p["resume_skill"]}*',
                        unsafe_allow_html=True,
                    )

        with col_b:
            missing = result["missing_skills"]
            st.markdown(f"### ❌ Missing Skills ({len(missing)})")
            if missing:
                chips = " ".join(
                    f'<span class="skill-chip chip-red">{s}</span>' for s in missing
                )
                st.markdown(chips, unsafe_allow_html=True)
            else:
                st.success("No missing skills — great!")

            overused = result["overused_keywords"]
            if overused:
                st.markdown(f"### ⚠ Overused Keywords ({len(overused)})")
                chips = " ".join(
                    f'<span class="skill-chip chip-yellow">{s}</span>' for s in overused
                )
                st.markdown(chips, unsafe_allow_html=True)

        st.markdown("---")

        # ── Section 2: Gaps ──────────────────────────────────────────────
        st.markdown("## ⚠ Gap Analysis")
        gaps = result["gaps"]
        if not gaps:
            st.success("No major gaps detected!")
        else:
            priority_icons = {
                "required": ("🔴", "priority-high"),
                "high": ("🔴", "priority-high"),
                "preferred": ("🟡", "priority-med"),
                "medium": ("🟠", "priority-med"),
                "general": ("🔵", "priority-low"),
            }
            for gap in gaps[:15]:
                icon, css_class = priority_icons.get(gap["priority"], ("•", ""))
                st.markdown(f"""
                <div class="gap-card {css_class}">
                    <b>{icon} [{gap['type'].upper()}] {gap['item']}</b><br>
                    <small>{gap['reason']}</small>
                </div>
                """, unsafe_allow_html=True)

        weak = result["weak_bullets"]
        if weak:
            st.markdown(f"### ⚠ Weak Bullet Points ({len(weak)})")
            for b in weak:
                st.markdown(
                    f'<div class="weak-bullet">"{b[:120]}{"..." if len(b) > 120 else ""}"</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # ── Section 3: Priority Actions ──────────────────────────────────
        st.markdown("## 🔴 Priority Actions")
        actions = result["suggestions"]["priority_actions"]
        if actions:
            for i, action in enumerate(actions, 1):
                st.markdown(
                    f'<div class="action-item"><b>{i}.</b> {action}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.success("No urgent actions needed!")

        st.markdown("---")

        # ── Section 4: Bullet Rewrites ───────────────────────────────────
        st.markdown("## ✏ Bullet Point Rewrites")
        bi = result["suggestions"]["bullet_improvements"]
        if not bi:
            st.success("No weak bullet points detected!")
        else:
            for item in bi:
                with st.expander(f"⚠ \"{item['original'][:70]}...\""):
                    st.markdown(f"**Issue:** {item['issue']}")
                    st.markdown(f"**Suggestion:** {item['suggestion']}")
                    st.info(f"💡 {item['example']}")

        st.markdown("---")

        # ── Section 5: Tips ──────────────────────────────────────────────
        st.markdown("## 💡 Improvement Tips")
        col_tip1, col_tip2 = st.columns(2)
        with col_tip1:
            st.markdown("#### 🏗 Structural Tips")
            for tip in result["suggestions"]["structural_tips"]:
                st.markdown(f"▸ {tip}")
            st.markdown("#### 💼 Experience Tips")
            for tip in result["suggestions"]["experience_tips"]:
                st.markdown(f"▸ {tip}")

        with col_tip2:
            st.markdown("#### 🔑 Keyword Optimization")
            for kw in result["suggestions"]["keyword_suggestions"]:
                st.markdown(f"▸ {kw}")
            st.markdown("#### ⚡ General Tips")
            for tip in result["improvement_tips"]:
                st.markdown(f"▸ {tip}")

        st.markdown("---")

        # ── Section 6: JSON Export ───────────────────────────────────────
        st.markdown("## 📥 JSON Report Export")
        json_str = json.dumps(result, indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇ Download JSON Report",
            data=json_str,
            file_name="ats_scan_report.json",
            mime="application/json",
        )
        with st.expander("View Full JSON Report"):
            st.code(json_str, language="json")


