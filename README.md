# AI-Powered Business Opportunity Finder

Streamlit app for scraping recent business listings and ranking the strongest opportunities with an OpenAI-compatible endpoint.

## Features

- Scrapes listings from a target URL.
- Filters listings to posts from the last 7 days.
- Lets users enter custom recommendation criteria.
- Includes criteria presets for quick analysis modes.
- Sends filtered listings to an OpenAI-compatible API for ranking.
- Shows raw listings and top recommendations in the UI.
- Shows page-by-page scraping progress and status updates.
- Provides downloadable CSV files for all listings, recent listings, and AI recommendations.
- Includes a local fallback ranker when no API key is configured.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add the API key from Luke:

```text
OPENAI_BASE_URL=https://three-mistress-opera-locations.trycloudflare.com/v1
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=smart
```

## Run

```bash
streamlit run app.py
```

## Using The App

1. Confirm the target URL in the sidebar (default points to SEEK last-7-days listings).
2. Set a safety page cap and click **Scrape recent listings**.
3. Watch live progress updates while pages are scraped.
4. Review the **Recent listings** and **All scraped listings** tabs.
5. Choose a criteria preset (or edit the prompt manually).
6. Click **Rank opportunities with AI** to produce top recommendations.
7. Export results via CSV download buttons.

The app is prefilled with the SEEK Business last-7-days URL:

```text
https://www.seekbusiness.com.au/businesses-for-sale?d=7&pg=1
```

For SEEK, pagination uses the `pg` query parameter. The app can scrape up to the selected safety page cap and stops early when a page returns no new listings.

## Live Test Notes

Before coding against the real target website, confirm with Luke:

- The exact target website or search URL.
- Which listing fields are expected.
- The date format used on the site.
- What criteria define a strong opportunity.
- Whether the site requires login or has scraping restrictions.

## Scraper Configuration

The sidebar accepts optional CSS selectors:

- Listing card selector
- Title selector
- Company selector
- Description selector
- Posted date selector
- Link selector

If selectors are empty, the app attempts to infer common listing card structures such as `article`, card-like containers, result rows, and list items. For best results during the assessment, inspect the target website and provide the exact selectors.

## Scope

This project is intentionally small for a 3-hour live coding assessment. It avoids databases, authentication, complex browser automation, and multi-site scraping abstractions unless the target site specifically requires them.
