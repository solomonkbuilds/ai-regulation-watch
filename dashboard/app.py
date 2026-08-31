"""
Streamlit dashboard for AI Reg Watch.

Run with:
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from src import storage  # noqa: E402

st.set_page_config(page_title="AI Reg Watch", layout="wide")

st.title("AI Reg Watch")
st.caption("Tracking regulatory changes across standards, with AI-relevance classification")

storage.init_db()

with storage.get_conn() as conn:
    changes = storage.list_changes(conn)
    sources = {row["id"]: row["name"] for row in conn.execute("SELECT id, name FROM sources")}

if not changes:
    st.info(
        "No changes recorded yet. Run `python -m src.main` to fetch sources and "
        "populate the database."
    )
    st.stop()

df = pd.DataFrame(changes)
df["source_name"] = df["source_id"].map(sources).fillna(df["source_id"])
df["detected_at"] = pd.to_datetime(df["detected_at"])

col1, col2, col3 = st.columns(3)
col1.metric("Total changes tracked", len(df))
col2.metric("AI-relevant changes", int(df["ai_relevant"].sum()))
col3.metric("Sources monitored", df["source_id"].nunique())

st.divider()

filter_col1, filter_col2 = st.columns([1, 1])
with filter_col1:
    only_ai = st.checkbox("Show AI-relevant changes only", value=False)
with filter_col2:
    selected_sources = st.multiselect(
        "Filter by source", options=sorted(df["source_name"].unique())
    )

filtered = df.copy()
if only_ai:
    filtered = filtered[filtered["ai_relevant"] == 1]
if selected_sources:
    filtered = filtered[filtered["source_name"].isin(selected_sources)]

st.subheader(f"Changes ({len(filtered)})")

for _, row in filtered.sort_values("detected_at", ascending=False).iterrows():
    is_simulated = str(row["change_summary"] or "").startswith("[SIMULATED")
    badge = "🟣 AI-relevant" if row["ai_relevant"] else "⚪ Not AI-relevant"
    sim_badge = " 🧪 SIMULATED (demo/test data)" if is_simulated else ""
    with st.expander(
        f"{row['detected_at'].strftime('%Y-%m-%d %H:%M UTC')} — {row['source_name']} — {badge}{sim_badge}"
    ):
        if is_simulated:
            st.warning(
                "This is a simulated change used to test the pipeline end-to-end. "
                "It is not a real detected regulatory update."
            )
        st.markdown(f"**Summary:** {row['change_summary'] or '_not classified_'}")
        if row["ai_relevant"]:
            st.markdown(f"**Category:** `{row['ai_relevance_category']}`")
            st.markdown(f"**Confidence:** {row['confidence']}")
            st.markdown(f"**Reasoning:** {row['reasoning']}")
        st.markdown("**Raw diff:**")
        st.code(row["diff_text"], language="diff")
