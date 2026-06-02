import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from recommender import rank_opportunities
from scraper import ListingSelectors, filter_recent_listings, scrape_listings


load_dotenv()


st.set_page_config(
    page_title="AI Business Opportunity Finder",
    page_icon=":mag:",
    layout="wide",
)


DEFAULT_CRITERIA = """Recommend businesses that look worth investigating.
Prioritize strong commercial intent, recent activity, clear demand signals,
specific business details, and opportunities where a follow-up could lead to revenue.
"""

CRITERIA_PRESETS = {
    "Balanced (default)": DEFAULT_CRITERIA,
    "Fast Flip / Resale": (
        "Prioritize businesses with strong immediate cash flow, simple operations, "
        "clear owner transition potential, and lower operational complexity."
    ),
    "Long-Term Growth": (
        "Prioritize listings with recurring revenue potential, expansion room, "
        "brand differentiation, and long-term defensibility."
    ),
    "Low-Risk Operator": (
        "Prioritize proven businesses with stable demand, transparent details, "
        "lower staffing complexity, and realistic entry pricing."
    ),
}


def _download_df_button(df: pd.DataFrame, label: str, file_name: str) -> None:
    if df.empty:
        return
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
    )


def render_listing_card(recommendation: dict) -> None:
    title = recommendation.get("title", "Untitled listing")
    score = recommendation.get("score", "N/A")
    reason = recommendation.get("reason", "No reason provided.")
    next_step = recommendation.get("suggested_next_step", "Review the original listing.")
    listing_url = recommendation.get("url")

    with st.container(border=True):
        st.subheader(f"{title} - Score: {score}/10")
        st.write(reason)
        st.caption(f"Suggested next step: {next_step}")
        if listing_url:
            st.link_button("Open listing", listing_url)


st.title("AI-Powered Business Opportunity Finder")
st.write(
    "Scrape recent listings from a target website, filter them to the last 7 days, "
    "and use AI to rank the most promising opportunities."
)

with st.sidebar:
    st.header("Scraper Settings")
    target_url = st.text_input(
        "Target listings URL",
        value="https://www.seekbusiness.com.au/businesses-for-sale?d=7&pg=1",
    )
    scrape_all_pages = st.checkbox("Scrape all available pages", value=True)
    max_pages = st.number_input(
        "Safety page cap",
        min_value=1,
        max_value=250,
        value=250 if scrape_all_pages else 25,
        help="The scraper stops early when a page has no new listings.",
    )
    max_rank_results = st.slider(
        "Max listings to send to AI",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
    )

    st.divider()
    st.subheader("CSS Selectors")
    st.caption(
        "Use these once the target website is known. The defaults try to infer listing cards."
    )
    listing_selector = st.text_input("Listing card selector", value="")
    title_selector = st.text_input("Title selector", value="")
    company_selector = st.text_input("Company selector", value="")
    description_selector = st.text_input("Description selector", value="")
    date_selector = st.text_input("Posted date selector", value="")
    link_selector = st.text_input("Link selector", value="a")

    st.divider()
    st.subheader("OpenAI-Compatible Endpoint")
    st.text_input(
        "OPENAI_BASE_URL",
        value=os.getenv(
            "OPENAI_BASE_URL",
            "https://three-mistress-opera-locations.trycloudflare.com/v1",
        ),
        key="base_url",
    )
    st.text_input(
        "OPENAI_API_KEY",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        key="api_key",
        help="Luke will provide this key via Discord.",
    )
    st.text_input(
        "Model name",
        value=os.getenv("OPENAI_MODEL", "smart"),
        key="model",
        help="Use smart for the locally hosted LLM unless Luke provides a different model.",
    )

preset = st.selectbox("Criteria preset", list(CRITERIA_PRESETS.keys()), index=0)
criteria = st.text_area(
    "Recommendation criteria",
    value=CRITERIA_PRESETS[preset],
    height=140,
)

selectors = ListingSelectors(
    listing=listing_selector or None,
    title=title_selector or None,
    company=company_selector or None,
    description=description_selector or None,
    date=date_selector or None,
    link=link_selector or None,
)

scrape_clicked = st.button("Scrape recent listings", type="primary", disabled=not target_url)
clear_clicked = st.button("Clear results")

if clear_clicked:
    for key in ("scraped_listings", "recent_listings", "recommendations"):
        st.session_state.pop(key, None)

if scrape_clicked:
    progress_bar = st.progress(0)
    status_box = st.empty()
    log_box = st.empty()
    scrape_logs = []

    def update_scrape_progress(status: dict) -> None:
        page = int(status.get("page_number", 0))
        progress_bar.progress(min(page / max_pages, 1.0))

        message = (
            f"Page {page} of up to {max_pages} | "
            f"{status.get('cards_found', 0)} cards found | "
            f"{status.get('total_listings', 0)} total listings | "
            f"{status.get('status', 'Scraping...')}"
        )
        status_box.info(message)

        scrape_logs.append(f"{message}\n{status.get('page_url', '')}")
        log_box.code("\n\n".join(scrape_logs[-10:]))

    try:
        scraped = scrape_listings(
            target_url,
            selectors=selectors,
            max_pages=max_pages,
            progress_callback=update_scrape_progress,
        )
        recent = filter_recent_listings(scraped, days=7)
        st.session_state["scraped_listings"] = scraped
        st.session_state["recent_listings"] = recent
        progress_bar.progress(1.0)
        status_box.success(
            f"Scraping complete. Found {len(scraped)} total listings, "
            f"{len(recent)} within the last 7 days."
        )
    except Exception as exc:
        status_box.empty()
        st.error(f"Scraping failed: {exc}")

scraped_listings = st.session_state.get("scraped_listings", [])
recent_listings = st.session_state.get("recent_listings", [])

if scraped_listings:
    col_total, col_recent, col_ratio = st.columns(3)
    col_total.metric("Total Scraped", len(scraped_listings))
    col_recent.metric("Within 7 Days", len(recent_listings))
    ratio = (len(recent_listings) / len(scraped_listings) * 100) if scraped_listings else 0
    col_ratio.metric("Recent Ratio", f"{ratio:.1f}%")

    st.success(
        f"Found {len(scraped_listings)} total listings. "
        f"{len(recent_listings)} are within the last 7 days."
    )

    tab_recent, tab_all = st.tabs(["Recent listings", "All scraped listings"])

    with tab_recent:
        if recent_listings:
            recent_df = pd.DataFrame(recent_listings)
            st.dataframe(recent_df, width="stretch")
            _download_df_button(recent_df, "Download recent listings CSV", "recent_listings.csv")
        else:
            st.warning(
                "No listings matched the last-7-days filter. Check the date selector or target URL."
            )

    with tab_all:
        all_df = pd.DataFrame(scraped_listings)
        st.dataframe(all_df, width="stretch")
        _download_df_button(all_df, "Download all listings CSV", "all_listings.csv")

if recent_listings:
    st.divider()
    rank_clicked = st.button("Rank opportunities with AI")

    if rank_clicked:
        with st.spinner("Ranking opportunities..."):
            try:
                recommendations = rank_opportunities(
                    recent_listings[:max_rank_results],
                    criteria=criteria,
                    api_key=st.session_state.get("api_key"),
                    base_url=st.session_state.get("base_url"),
                    model=st.session_state.get("model"),
                )
                st.session_state["recommendations"] = recommendations
            except Exception as exc:
                st.session_state["recommendations"] = []
                st.error(f"AI ranking failed: {exc}")
                st.info(
                    "Use model smart for the local LLM, or ask Luke for the exact model ID."
                )

recommendations = st.session_state.get("recommendations", [])

if recommendations:
    st.header("Top Recommendations")
    rec_df = pd.DataFrame(recommendations)
    st.dataframe(rec_df, width="stretch")
    _download_df_button(rec_df, "Download recommendations CSV", "recommendations.csv")
    for recommendation in recommendations:
        render_listing_card(recommendation)
elif target_url and not scraped_listings:
    st.info("Enter the target site details, then scrape listings to begin.")
