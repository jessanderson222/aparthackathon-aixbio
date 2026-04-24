"""
BioWatch Brief — Streamlit UI
Run with:  streamlit run app.py
"""

import streamlit as st
from pipeline import assess

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BioWatch Brief",
    page_icon="🧬",
    layout="wide",
)

# ─── Minimal custom CSS ────────────────────────────────────────────────────────

st.markdown("""
<style>
  .risk-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 1.1rem;
    letter-spacing: 0.04em;
  }
  .r1 { background:#e8f5e9; color:#1b5e20; }
  .r2 { background:#fff9c4; color:#4e3900; }
  .r3 { background:#fff3e0; color:#5d2e00; }
  .r4 { background:#fce4ec; color:#880e2a; }
  .r5 { background:#b71c1c; color:#fff; }
  .flag-pill {
    display: inline-block;
    background: #f3f0ff;
    color: #4a1d8a;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.78rem;
    margin: 2px 2px;
  }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("🧬 BioWatch Brief")
st.caption(
    "Paste an incident report — ProMED alert, WHO Disease Outbreak News item, "
    "news article, or field note — and receive a structured rapid-assessment card."
)
st.warning(
    "⚠️ This tool provides an **initial rapid assessment only** and is not a substitute "
    "for official public health authority analysis or laboratory confirmation.",
    icon="⚠️",
)

# ─── Input ────────────────────────────────────────────────────────────────────

report = st.text_area(
    "Incident report",
    height=200,
    placeholder="Paste the text of a ProMED alert, WHO DONS item, news article, or lab note here…",
)

col_btn, col_spacer = st.columns([1, 4])
with col_btn:
    run = st.button("Analyse →", type="primary", use_container_width=True)

# ─── Run pipeline ─────────────────────────────────────────────────────────────

if run:
    if not report.strip():
        st.error("Please paste an incident report before running.")
        st.stop()

    with st.spinner("Assessing… this usually takes 10–20 seconds."):
        try:
            card = assess(report)
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    # ── Risk level badge ──────────────────────────────────────────────────────

    level_num = card["risk_level"].split("-")[0]  # "3" from "3-moderate"
    level_label = card["risk_level"].split("-", 1)[1].title()
    badge_class = f"r{level_num}"

    st.divider()
    st.subheader("Risk Assessment Card")

    col_level, col_rationale = st.columns([1, 3])
    with col_level:
        st.markdown(
            f'<div style="text-align:center;padding:16px 0">'
            f'<div style="font-size:0.75rem;color:#888;margin-bottom:6px">RISK LEVEL</div>'
            f'<span class="risk-badge {badge_class}">{level_num} — {level_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_rationale:
        st.info(card["risk_rationale"])

    st.divider()

    # ── Two-column layout for the main fields ─────────────────────────────────

    left, right = st.columns(2)

    with left:
        # Pathogen summary
        ps = card["pathogen_summary"]
        st.markdown("**🦠 Pathogen**")
        st.markdown(
            f"**{ps['name']}** · {ps['type'].title()} · *{ps['known_or_novel'].replace('-', ' ')}*"
        )
        for char in ps.get("key_characteristics", []):
            st.markdown(f"- {char}")

        st.markdown("**📡 Transmission**")
        tx = card["transmission"]
        st.markdown(
            f"Human-to-human: **{tx['human_to_human'].replace('-', ' ')}**"
        )
        for route in tx.get("routes", []):
            st.markdown(f"- {route}")

        st.markdown("**👥 Affected populations**")
        for pop in card.get("affected_populations", []):
            st.markdown(f"- {pop}")

    with right:
        # Geographic scope
        geo = card["geographic_scope"]
        st.markdown("**🗺️ Geographic scope**")
        st.markdown(
            f"Trajectory: **{geo['spread_trajectory'].replace('-', ' ').title()}**"
        )
        for loc in geo.get("current_locations", []):
            st.markdown(f"- {loc}")

        # Regulatory context
        reg = card["regulatory_context"]
        st.markdown("**⚖️ Regulatory context**")
        st.markdown(f"Select agent status: **{reg['select_agent_status']}**")
        st.markdown(f"IHR notification: **{reg['ihr_notification'].replace('-', ' ').title()}**")
        for fw in reg.get("relevant_frameworks", []):
            st.markdown(f"- {fw}")

    st.divider()

    # ── Recommended actions ───────────────────────────────────────────────────

    PRIORITY_COLORS = {
        "immediate": "🔴",
        "24-48h": "🟡",
        "this-week": "🟢",
    }

    st.markdown("**✅ Recommended actions**")
    for action in card.get("recommended_actions", []):
        icon = PRIORITY_COLORS.get(action["priority"], "⚪")
        st.markdown(
            f"{icon} **[{action['priority'].upper()}]** {action['action']} "
            f"<span style='color:#888;font-size:0.85rem'>— {action['actor']}</span>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Uncertainty flags ─────────────────────────────────────────────────────

    flags = card.get("uncertainty_flags", [])
    if flags:
        st.markdown("**⚠️ Uncertainty flags**")
        pills = "".join(
            f'<span class="flag-pill">{f["field"]}: {f["flag"].replace("-", " ")}</span>'
            for f in flags
        )
        st.markdown(pills, unsafe_allow_html=True)
        with st.expander("Flag details"):
            for f in flags:
                st.markdown(f"- **{f['field']}** ({f['flag']}): {f['note']}")

    # ── Sources ───────────────────────────────────────────────────────────────

    sources = card.get("sources_referenced", [])
    if sources:
        with st.expander("📎 Sources referenced in input"):
            for s in sources:
                st.markdown(f"- {s}")

    # ── Raw JSON (for judges / debugging) ────────────────────────────────────

    with st.expander("🔍 Raw JSON output"):
        st.json(card)
