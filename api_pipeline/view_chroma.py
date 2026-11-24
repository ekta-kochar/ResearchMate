"""Read-only local browser for ResearchMate's persistent ChromaDB collection."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from researchmate import ChromaPaperStore


st.set_page_config(page_title="ResearchMate Paper Database", layout="wide")
st.title("ResearchMate paper database")
st.caption("Read-only view of the local ChromaDB collection, including stored metadata and provenance.")


def brief(record: dict, distance: float | None = None) -> dict:
    row = {
        "Title": record.get("title") or "(untitled)",
        "Year": record.get("year") or "",
        "Source": record.get("source") or "",
        "DOI": record.get("doi") or "",
        "Abstract": "Yes" if record.get("abstract") else "No",
        "Keywords": ", ".join(record.get("keywords") or []),
    }
    if distance is not None:
        row["Cosine distance"] = round(float(distance), 4)
    return row


try:
    with ChromaPaperStore() as store:
        total = store.count()
        records = store.get_records()
except Exception as exc:
    st.error(f"Could not open the local paper database: {exc}")
    st.info("Run this page from the api_pipeline folder with its virtual environment active, and confirm chroma_db exists.")
    st.stop()

if not records:
    st.warning("The collection is empty. Search papers and store them with ChromaPaperStore.upsert_records(...) first.")
    st.stop()

sources = sorted({str(record.get("source") or "Unknown") for record in records})
left, middle, right = st.columns(3)
left.metric("Papers in ChromaDB", total)
middle.metric("Sources represented", len(sources))
right.metric("Records with abstracts", sum(bool(record.get("abstract")) for record in records))

st.sidebar.header("Find papers")
mode = st.sidebar.radio("View", ["Browse records", "Semantic search"])
selected_source = st.sidebar.selectbox("Source", ["All sources", *sources])
source_filter = None if selected_source == "All sources" else selected_source

if mode == "Semantic search":
    search_text = st.sidebar.text_input("Describe the paper you need")
    result_count = st.sidebar.slider("Number of results", min_value=1, max_value=20, value=5)
    if search_text.strip():
        try:
            with ChromaPaperStore() as store:
                matches = store.query_papers(
                    search_text,
                    n_results=result_count,
                    where={"source": source_filter} if source_filter else None,
                )
            visible = [match["record"] for match in matches]
            st.subheader("Closest matches")
            st.caption("Cosine distance is a measure of difference: lower values indicate closer matches.")
            st.dataframe(pd.DataFrame([brief(match["record"], match["distance"]) for match in matches]),
                         use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Search failed: {exc}")
    else:
        visible = [record for record in records if not source_filter or record.get("source") == source_filter]
        st.info("Enter a phrase in the sidebar to search by meaning.")
else:
    visible = [record for record in records if not source_filter or record.get("source") == source_filter]
    st.subheader("Stored papers")
    st.dataframe(pd.DataFrame([brief(record) for record in visible]), use_container_width=True, hide_index=True)

if visible:
    labels = {f"{record.get('title') or '(untitled)'} — {record.get('source') or 'Unknown'} — {record.get('canonical_id') or record.get('source_id') or ''}": record for record in visible}
    chosen = st.selectbox("Open a paper record", list(labels))
    paper = labels[chosen]
    st.subheader(paper.get("title") or "Untitled paper")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**Year:** {paper.get('year') or 'Unknown'}")
    c2.write(f"**Source:** {paper.get('source') or 'Unknown'}")
    c3.write(f"**DOI:** {paper.get('doi') or 'Not available'}")
    if paper.get("url"):
        st.markdown(f"[Open paper record]({paper['url']})")
    st.write("**Authors:** " + (", ".join(paper.get("authors") or []) or "Not available"))
    st.write("**Keywords:** " + (", ".join(paper.get("keywords") or []) or "Not available"))
    st.markdown("**Abstract**")
    st.write(paper.get("abstract") or "No abstract is stored for this paper.")
    with st.expander("Metadata provenance"):
        st.json(paper.get("provenance") or {}, expanded=False)
    with st.expander("Metadata conflicts"):
        st.json(paper.get("metadata_conflicts") or {}, expanded=False)
    with st.expander("Complete stored record"):
        st.code(json.dumps(paper, ensure_ascii=False, indent=2), language="json")
