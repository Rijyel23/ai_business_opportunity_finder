# Technical Assessment: AI-Powered Business Opportunity Finder

**Position:** Developer Candidate (Trial)

**Time Allotment:** 3 Hours

**Environment:** Discord Live Stream (Full Screen Share)

**Point of Contact:** Luke (Available via Discord Chat)

---

## 1. Project Objective

The goal of this assessment is to build a Python-based discovery tool. The application must scrape business listings from a designated platform—specifically focusing on data from the **last 7 days**—and utilize AI logic to provide **recommendations** on which businesses are worth investigating based on user-defined criteria.

**Core Requirement:** This is an AI-assisted development test. You are expected to use AI tooling to assist in the architecture, coding, data analysis logic, and refactoring of the project. **For development assistance, you may use whichever AI development tools you already have available** (e.g., your own IDE assistant, CLI agent, or chat-based tools).

Separately, to power the **AI logic inside the application you build** (the recommendation engine), we will supply an **API key for our locally hosted model**. This key is intended for integration into your application—not for your development tooling.

---

## 2. Technical Requirements

### Stack & Tools

- **Language:** Python 3.10+

- **UI Framework:** Use any Python-based framework (e.g., Streamlit, Flask, or Gradio).

- **Development Tooling:** Use your own AI development tools if you have them available. Any AI assistant or agent is acceptable—the choice is yours.

- **In-App AI Integration:** Integrate the **AI logic of your application** using the API key we provide for our locally hosted model. The endpoint is **OpenAI-compatible** (served via LiteLLM), so you can connect using any OpenAI-compatible client/SDK.
  
  - **Connection details**
    -  OPENAI_BASE_URL=https://three-mistress-opera-locations.trycloudflare.com/v1
    - Your API key will delivered via Discord from Luke
    - Model will automatically be routed, so no need to set this. 

### Scope of Work

- **Time-Sensitive Scraping:** Build a scraper to extract listings posted within the **last 7 days** from the target site.

- **Recommendation Engine:** Implement logic (AI-driven or algorithmic) that analyzes the scraped data and "flags" or "recommends" specific businesses to the user based on their input criteria.

- **UI & Filtering:** Create an interface where users can input their preferences and view both the raw filtered data and the "Top Recommendations."

### Communication & Clarification

If you have any questions regarding the project scope, the specific target website, or the **criteria used to define a "recommendation,"** please reach out to **Luke** in the Discord chat. Requesting clarification or seeking further information from Luke is encouraged and will not negatively impact your assessment.

---

## 3. Operational Rules

- **Live Stream:** You must remain in the designated Discord channel and share your **entire screen** (Terminal, IDE, Browser, and AI interactions) for the full 180 minutes.

- **Progress Monitoring:** The SGPS team will monitor your workflow and your ability to manage the project and time constraints effectively.
