# Mutual Fund Analyzer

A deployed Indian mutual-fund research application that turns a selection of **2–10 schemes** into an AI-written, ranked PDF report. It uses live AMFI scheme data and historical NAVs, calculates the financial metrics in Python, and uses an LLM for the executive summary and fund-wise ranking explanations.

**Live app:** https://mutual-fund-analyzer-rho.vercel.app  
**Backend health:** https://mutual-fund-analyzer-api-bqho.onrender.com/health

## What it does

### Multi-fund PDF report
- Search the live AMFI scheme master and select 2–10 schemes.
- Paste a custom list of scheme names (one per line, comma or semicolon separated).
- Choose a 1, 3, 5, or 10-year analysis period.
- Fetch historical NAV data for every selected scheme.
- Calculate total return, CAGR, annualized volatility, and maximum drawdown.
- Rank the selected funds using a disclosed composite risk/return score.
- Ask the LLM to write the executive summary and evidence-based reason for each ranking position.
- Download a formatted A4 PDF with the comparison table, ranking, individual scheme details, data-quality notes, methodology, and disclaimer.

### AI assistant
The original single-fund conversational analysis remains available in the AI Assistant tab.

## Ranking methodology

The ranking is intentionally transparent and reproducible. Each metric is min-max normalized within the funds selected for that report:

| Metric | Weight | Preferred direction |
|---|---:|---|
| CAGR | 40% | Higher |
| Annualized volatility | 30% | Lower |
| Maximum drawdown | 30% | Shallower / less negative |

The LLM produces the final ranking and writes the reasons using the supplied figures and composite scores. Its returned scheme order is validated to ensure every selected scheme appears exactly once. If the LLM is unavailable or returns an invalid ranking, the application falls back to the deterministic composite-score order. Scores are **relative to the selected funds**, not universal ratings or forecasts. Comparisons across different fund categories may not be like-for-like.

## Data sources and calculation policy

- **Primary source:** AMFI public scheme master and historical NAV archive.
- **Fallback:** MFapi.in, used when AMFI historical retrieval is unavailable or insufficient.
- All reported metrics are calculated by this application from NAV observations.
- Invalid/non-positive NAVs are discarded; identical same-date observations are deduplicated; conflicting same-date NAVs are rejected.
- Volatility is the sample standard deviation of consecutive NAV returns annualized by √252.
- Maximum drawdown is the largest peak-to-subsequent-trough decline in the selected NAV series.
- The application reports observation counts, return-interval counts, calendar gaps, and whether the latest historical NAV reconciles with the current AMFI scheme-master NAV/date.
- Benchmark TRI data is not yet integrated. Consequently, benchmark-relative alpha, beta, Sharpe ratio, information ratio, and market-capture ratios are not presented.

Historical performance is not a guarantee of future returns. This application provides informational research and is not personalized investment advice.

## Architecture

- **Frontend:** Next.js 16, React 19, html2pdf.js; deployed on Vercel.
- **Backend:** Python, FastAPI; deployed on Render.
- **AI orchestration:** LangGraph.
- **LLM:** Groq, openai/gpt-oss-120b.
- **NAV ingestion:** AMFI with MFapi.in fallback.
- **CI:** GitHub Actions runs backend NAV and comparison tests on relevant pushes and pull requests.

## API

### GET /health
Returns backend health status.

### GET /funds/search?q=<text>&limit=20
Searches the current AMFI scheme master. The response contains scheme name, scheme code, ISIN, plan/option, latest NAV, and NAV date.

### POST /compare
Request:
~~~json
{
  "fund_names": [
    "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
    "HDFC Flexi Cap Fund - Direct Plan - Growth"
  ],
  "period": 1
}
~~~
Supported periods: 1, 3, 5, and 10. The endpoint requires 2–10 distinct schemes and fails the report rather than silently ranking an incomplete set if any selected scheme cannot be resolved or lacks sufficient NAV history.

### POST /chat
Accepts message, optional fund_names, and optional period for the conversational analysis flow.

## Run locally

### Requirements
- Node.js 20+
- Python 3.10+
- Groq API key

### Backend
~~~bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
~~~

Create backend/.env:
~~~env
GROQ_API_KEY=your_groq_api_key
~~~

Start the API:
~~~bash
uvicorn main:app --reload --port 8000
~~~

### Frontend
In a second terminal:
~~~bash
cd frontend
npm install
~~~

Create frontend/.env.local:
~~~env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
~~~

Start Next.js:
~~~bash
npm run dev
~~~

Open http://localhost:3000.

## Tests

From the backend directory:
~~~bash
python -m pytest -q tests
~~~

GitHub Actions runs the NAV analytics and multi-fund ranking tests automatically when backend files or the workflow change.

## Deployment

- Frontend production project: Vercel, root directory frontend.
- Backend service: Render, start command cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT.
- Backend environment variable: GROQ_API_KEY.
- Frontend environment variable: NEXT_PUBLIC_BACKEND_URL=https://mutual-fund-analyzer-api-bqho.onrender.com.

Never commit API keys or local .env files.

## Take-home submission notes

- Live URL and repository: available above.
- Sample PDF: generate from the live app after deployment and include the downloaded PDF in the submission.
- AI coding session log: docs/AI_SESSION_LOG.md.
- Short demo walkthrough: docs/DEMO_SCRIPT.md.
- Time spent: record the actual hours in the submission form; this repository does not fabricate a time estimate.

## Disclaimer

Past performance is not indicative of future returns. Mutual fund investments are subject to market risks. Read all scheme-related documents carefully. This tool is for informational research only and does not provide personalized investment advice.
