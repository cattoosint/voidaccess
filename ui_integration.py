"""
ui_integration.py — Phase 6 UI extension for VoidAccess.

Adds Phase 6 capabilities (stylometry, OPSEC analysis, temporal patterns,
translation, graph) to the Streamlit UI as non-destructive sidebar/tab panels.

This module is imported at the bottom of ui.py via:
    try:
        import ui_integration
    except ImportError:
        pass

When imported during a Streamlit run it adds new sections below the main
investigation output. If any Phase 6 module is missing the relevant section
silently does not render.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _adapt_scraped_pages(scraped_data: Any) -> list[dict]:
    """
    Normalize scraped session data into list[{"url": ..., "text": ...}].

    ui.py stores scraped pages as dict[url -> text]. Older/alternate callers may
    still pass list[dict], which is preserved when possible.
    """
    if isinstance(scraped_data, dict):
        return [
            {"url": str(url), "text": text or ""}
            for url, text in scraped_data.items()
        ]

    if isinstance(scraped_data, list):
        normalized: list[dict] = []
        for item in scraped_data:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "url": item.get("url") or item.get("link") or "",
                    "text": item.get("text") or item.get("content") or "",
                }
            )
        return normalized

    return []

# ---------------------------------------------------------------------------
# Render functions (called by the module-level hook below)
# ---------------------------------------------------------------------------


def render_stylometry_panel(investigation_id: Optional[int]) -> None:
    """
    Show style similarity matrix for all THREAT_ACTOR_HANDLE entities in
    the current investigation. Flags pairs above 0.85 similarity.
    """
    try:
        import streamlit as st
        from fingerprint.profiler import load_profiles_from_db
        from fingerprint.stylometry import are_likely_same_author, compute_similarity

        profiles = load_profiles_from_db(investigation_id)
        if not profiles:
            return

        handles = list(profiles.keys())
        if len(handles) < 2:
            return

        st.subheader("🔍 Writing Style Analysis", anchor=False)
        st.caption(
            "Compares writing patterns across discovered handles to identify "
            "possible shared authorship."
        )

        flagged: list[tuple[str, str, float]] = []
        rows = []
        for i, h1 in enumerate(handles):
            for h2 in handles[i + 1 :]:
                score = compute_similarity(profiles[h1], profiles[h2])
                rows.append({"Handle A": h1, "Handle B": h2, "Similarity": round(score, 3)})
                same, _ = are_likely_same_author(profiles[h1], profiles[h2])
                if same:
                    flagged.append((h1, h2, score))

        if flagged:
            st.warning(f"⚠️ {len(flagged)} possible same-author pair(s) detected")
            for h1, h2, score in flagged:
                st.markdown(
                    f"- **{h1}** ↔ **{h2}** — similarity `{score:.3f}` "
                    f"🏷️ *Possible Same Author*"
                )

        if rows:
            st.dataframe(rows, use_container_width=True)

    except Exception as exc:
        logger.debug("render_stylometry_panel: %s", exc)


def render_opsec_panel(investigation_id: Optional[int]) -> None:
    """
    Show OPSEC risk scores for all discovered threat actor handles.
    Color codes: red (high), orange (medium), green (low).
    """
    try:
        import streamlit as st
        from analysis.opsec import run_full_opsec_analysis
        from fingerprint.profiler import load_profiles_from_db

        profiles = load_profiles_from_db(investigation_id)
        if not profiles:
            return

        # Retrieve texts_with_timestamps from session_state pages if available
        scraped = st.session_state.get("scraped", [])
        if not scraped:
            return

        st.subheader("🛡️ OPSEC Analysis", anchor=False)
        st.caption("Detects operational security failures that may reveal actor identity.")

        for handle in list(profiles.keys())[:10]:
            texts_ts = [
                {"text": p.get("text", ""), "timestamp": None}
                for p in scraped
                if p.get("text")
            ]
            report = run_full_opsec_analysis(handle, texts_ts)
            level = report.get("risk_level", "low")
            score = report.get("risk_score", 0.0)

            color_map = {"high": "🔴", "medium": "🟠", "low": "🟢"}
            icon = color_map.get(level, "⚪")

            with st.expander(f"{icon} **{handle}** — Risk: {level.upper()} ({score:.2f})"):
                tz = report.get("timezone_leak", {})
                if tz.get("detected"):
                    st.markdown(
                        f"- **Timezone leak**: probable {tz.get('probable_timezone_offset')} "
                        f"(window: {tz.get('peak_window')})"
                    )
                lang = report.get("language_switch", {})
                if lang.get("detected"):
                    st.markdown(
                        f"- **Language switch**: {lang.get('switch_count')} outlier post(s) "
                        f"among {lang.get('languages_found')}"
                    )
                clearnet = report.get("clearnet_slips", {})
                if clearnet.get("detected"):
                    st.markdown(
                        f"- **Clearnet slips**: {clearnet.get('clearnet_urls')}"
                    )

    except Exception as exc:
        logger.debug("render_opsec_panel: %s", exc)


def render_temporal_panel(investigation_id: Optional[int]) -> None:
    """
    Show activity timeline charts and pattern check results for top entities.
    """
    try:
        import streamlit as st
        from analysis.patterns import run_all_patterns
        from analysis.temporal import build_activity_timeline

        if not investigation_id:
            return

        try:
            from db.models import Entity
            from db.session import get_session

            with get_session() as session:
                entities = (
                    session.query(Entity)
                    .filter(Entity.investigation_id == investigation_id)
                    .all()
                )
        except Exception:
            return

        if not entities:
            return

        st.subheader("📈 Temporal Analysis", anchor=False)
        st.caption("Activity timelines and behavioral pattern detection.")

        # Show top 5 most-seen entities
        seen_values: dict[str, str] = {}
        for e in entities:
            seen_values[e.value] = e.entity_type

        for value, etype in list(seen_values.items())[:5]:
            timeline = build_activity_timeline(value, etype)
            if not timeline:
                continue

            with st.expander(f"**{value}** ({etype})"):
                chart_rows = []
                for row in timeline:
                    if "date" in row and "count" in row:
                        chart_rows.append({"date": row["date"], "count": row["count"]})
                if chart_rows:
                    st.line_chart(chart_rows, x="date", y="count")

                patterns = run_all_patterns(value, etype)
                exit_risk = patterns.get("exit_scam", {}).get("risk", "low")
                le_risk = patterns.get("law_enforcement", {}).get("risk", "low")
                new_actor = patterns.get("new_actor", {}).get("is_new", False)
                anomalies = patterns.get("anomalies", [])

                if exit_risk == "high":
                    st.error(
                        f"🚨 Exit scam risk: HIGH — "
                        f"{patterns['exit_scam'].get('reason', '')}"
                    )
                if le_risk == "high":
                    st.error(
                        f"🚔 Law enforcement risk: HIGH — "
                        f"{patterns['law_enforcement'].get('reason', '')}"
                    )
                if new_actor:
                    st.info("🆕 New actor — first appeared within the last 7 days")
                if anomalies:
                    st.warning(f"⚠️ {len(anomalies)} anomalous day(s) detected in timeline")

    except Exception as exc:
        logger.debug("render_temporal_panel: %s", exc)


def render_translation_panel(pages: list[dict]) -> None:
    """
    If any scraped pages are non-English, show language breakdown and
    offer a 'Translate All' button.
    """
    try:
        import streamlit as st
        from i18n.detect import detect_language, is_non_english
        from i18n.translate import translate_batch

        non_english = [
            (i, p)
            for i, p in enumerate(pages)
            if p.get("text") and is_non_english(p["text"])
        ]

        if not non_english:
            return

        st.subheader("🌐 Multilingual Content", anchor=False)
        st.caption(
            f"{len(non_english)} of {len(pages)} scraped pages appear to be non-English."
        )

        # Language breakdown
        from collections import Counter

        lang_counts: Counter = Counter()
        for _, page in non_english:
            lang = detect_language(page.get("text", ""))
            if lang:
                lang_counts[lang] += 1

        if lang_counts:
            st.bar_chart(
                [{"language": lang, "pages": count} for lang, count in lang_counts.items()],
                x="language",
                y="pages",
            )

        if st.button("🔄 Translate All Non-English Pages"):
            with st.spinner("Translating…"):
                texts = [p.get("text", "") for _, p in non_english]
                translated = translate_batch(texts)
                for (idx, page), trans in zip(non_english, translated):
                    if trans:
                        with st.expander(f"Page {idx + 1}: {page.get('url', 'unknown')}"):
                            st.markdown(trans)

    except Exception as exc:
        logger.debug("render_translation_panel: %s", exc)


def render_graph_panel(investigation_id: Optional[int]) -> None:
    """
    If Phase 3 graph module is available, render an interactive pyvis graph
    and summary stats for the current investigation.
    """
    try:
        import streamlit as st
        import streamlit.components.v1 as components
        from graph.builder import build_graph_from_db
        from graph.export import summary_stats
        from graph.queries import get_actor_profile
        from graph.visualize import get_html_string

        if not investigation_id:
            return

        g = build_graph_from_db(investigation_id=investigation_id)
        if g is None or g.number_of_nodes() == 0:
            return

        st.subheader("🕸️ Entity Graph", anchor=False)

        stats = summary_stats(g)
        col1, col2, col3 = st.columns(3)
        col1.metric("Nodes", stats.get("total_nodes", 0))
        col2.metric("Edges", stats.get("total_edges", 0))
        col3.metric("Node types", len(stats.get("nodes_by_type", {})))

        html = get_html_string(g, max_nodes=200)
        if html:
            components.html(html, height=600, scrolling=True)

        # Node profile drill-down
        node_id = st.text_input("Node ID to inspect:", key="p6_graph_node_id")
        if node_id:
            profile = get_actor_profile(g, node_id)
            if profile:
                st.json(profile)
            else:
                st.warning(f"No profile found for node: {node_id}")

    except Exception as exc:
        logger.debug("render_graph_panel: %s", exc)


# ---------------------------------------------------------------------------
# Module-level hook — runs when ui.py does `import ui_integration`
# ---------------------------------------------------------------------------

def _render_phase6_panels() -> None:
    """Called at import time from ui.py to inject Phase 6 panels."""
    try:
        import streamlit as st

        # Only render if an investigation has been completed this session
        if not st.session_state.get("streamed_summary"):
            return

        investigation_id = st.session_state.get("investigation_id")
        scraped = _adapt_scraped_pages(st.session_state.get("scraped", {}))

        st.divider()
        st.markdown("### 🔬 Phase 6 — Advanced Intelligence")

        render_stylometry_panel(investigation_id)
        render_opsec_panel(investigation_id)
        render_temporal_panel(investigation_id)
        render_translation_panel(scraped)
        render_graph_panel(investigation_id)

    except Exception as exc:
        logger.debug("_render_phase6_panels: %s", exc)


_render_phase6_panels()
