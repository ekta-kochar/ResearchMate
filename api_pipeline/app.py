"""ResearchMate prototype: read papers from ChromaDB and chat over them."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from researchmate import ChromaPaperStore
from researchmate import search_all_sources
from researchmate.online_cache import cache_online_search, get_cached_online_search
from researchmate.ranking import rank_search_results


load_dotenv(Path(__file__).with_name(".env"))
st.set_page_config(page_title="ResearchMate", page_icon="📚", layout="wide")
st.title("📚 ResearchMate")
st.caption("Search your local paper database and ask questions grounded in the retrieved papers.")


def _paper_table(matches: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Rank": match["rank"],
                "Title": match["record"].get("title") or "(untitled)",
                "Year": match["record"].get("year") or "",
                "Source": match["record"].get("source") or "",
                "Score": round(match["final_score"], 3),
                "Semantic": round(match["semantic_score"], 3),
                "Keywords": round(match["keyword_score"], 3),
                "Recency": round(match["recency_score"], 3),
                "DOI": match["record"].get("doi") or "",
            }
            for match in matches
        ]
    )


def _paper_context(matches: list[dict[str, Any]], max_papers: int = 5) -> str:
    sections = []
    for index, match in enumerate(matches[:max_papers], start=1):
        paper = match["record"]
        abstract = paper.get("abstract") or "No abstract is stored."
        sections.append(
            f"[{index}] {paper.get('title') or 'Untitled'} "
            f"({paper.get('year') or 'year unknown'}; {paper.get('source') or 'source unknown'})\n"
            f"Authors: {', '.join(paper.get('authors') or []) or 'not listed'}\n"
            f"DOI: {paper.get('doi') or 'not available'}\n"
            f"Abstract: {abstract[:3000]}"
        )
    return "\n\n".join(sections)


try:
    with ChromaPaperStore() as store:
        database_count = store.count()
        stored_records = store.get_records() if database_count else []
except Exception as exc:
    st.error(f"Could not open the ResearchMate paper database: {exc}")
    st.info("Confirm ChromaDB is installed and api_pipeline/chroma_db contains the stored paper collection.")
    st.stop()

with st.sidebar:
    st.subheader("Paper database")
    st.metric("Stored papers", database_count)
    available_sources = sorted(
        {str(record.get("source") or "Unknown") for record in stored_records}
    )
    source_choice = st.selectbox("Limit to source", ["All sources", *available_sources])
    result_limit = st.slider("Papers to show", min_value=1, max_value=20, value=10)
    search_online = st.checkbox("Search online sources automatically", value=True)
    refresh_online = st.checkbox("Refresh online results even for cached questions", value=False)
    st.caption("Ranking: 70% semantic similarity · 20% keyword overlap · 10% recency")
    st.caption("Online results are standardized, deduplicated, and saved in this ChromaDB.")

if not database_count:
    st.warning("The paper database is empty. Ask a question with online search enabled to populate it.")

for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("matches"):
            st.dataframe(_paper_table(message["matches"]), use_container_width=True, hide_index=True)
        if message.get("online_status"):
            st.caption(message["online_status"])

question = st.chat_input("Ask a research question about the papers in your database…")
if question:
    history = st.session_state.setdefault("messages", [])
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    online_status = ""
    try:
        with ChromaPaperStore() as store:
            if search_online:
                try:
                    cached = get_cached_online_search(store.client, question)
                    if cached and not refresh_online:
                        online_status = (
                            "Online sources skipped: this exact question was already searched. "
                            f"Its results are in the database (last searched {cached.get('searched_at', 'previously')})."
                        )
                    else:
                        with st.spinner("Searching PubMed, arXiv, Crossref, Europe PMC, and OpenAlex; saving new records…"):
                            online_records = search_all_sources(question, max_results=5)
                            if online_records:
                                saved = store.upsert_records(online_records)
                                cache_online_search(store.client, question, saved)
                                online_status = (
                                    f"Online search found {len(online_records)} standardized records; "
                                    f"{saved} unique records were saved or updated in ChromaDB."
                                )
                            else:
                                online_status = "Online search returned no records; the database search will still run."
                except Exception as online_exc:
                    online_status = (
                        "Online lookup was unavailable; searching papers already in your database instead. "
                        f"Details: {online_exc}"
                    )

            # A network, cache, or ingestion failure should not prevent use of
            # papers that are already available in the local collection.
            database_count = store.count()
            matches = store.query_papers(
                question,
                n_results=database_count,
                where={"source": source_choice} if source_choice != "All sources" else None,
            ) if database_count else []
        ranked = rank_search_results(matches, question, top_n=result_limit)
        search_error = ""
    except Exception as exc:
        ranked = []
        search_error = str(exc)

    with st.chat_message("assistant"):
        if online_status:
            st.caption(online_status)
        if search_error:
            response_text = "I couldn't search the local paper database. Please check that the Chroma collection is available."
            st.error(response_text)
            st.caption(search_error)
        elif not ranked:
            response_text = "No matching papers were found in the selected database source."
            st.info(response_text)
        else:
            st.markdown("### Ranked papers")
            st.dataframe(_paper_table(ranked), use_container_width=True, hide_index=True)
            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                response_text = (
                    "I found and ranked papers in your database. To generate an answer "
                    "from their abstracts, configure GROQ_API_KEY locally; the ranked results above are available now."
                )
                st.info(response_text)
            else:
                try:
                    from groq import Groq

                    system_prompt = (
                        "You are ResearchMate, an academic research assistant. Answer the user's question "
                        "using the supplied paper records. Prioritize their abstracts, do not invent findings "
                        "or citations, and state when the records do not contain enough evidence. Cite papers "
                        "as [1], [2], etc. using the supplied numbering. Distinguish evidence from inference.\n\n"
                        f"Retrieved papers:\n{_paper_context(ranked)}"
                    )
                    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
                    prior = [
                        {"role": item["role"], "content": item["content"]}
                        for item in history[:-1]
                        if item["role"] in {"user", "assistant"}
                    ]
                    completion = Groq(api_key=groq_key).chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            *prior,
                            {"role": "user", "content": question},
                        ],
                        temperature=0.3,
                        max_completion_tokens=1200,
                    )
                    response_text = completion.choices[0].message.content or "No answer text was returned."
                    st.markdown(response_text)
                except Exception:
                    response_text = "The papers were retrieved, but the assistant could not generate a response. Check the local Groq key, model setting, and network access."
                    st.error(response_text)
        history.append(
            {
                "role": "assistant",
                "content": response_text,
                "matches": ranked,
                "online_status": online_status,
            }
        )
