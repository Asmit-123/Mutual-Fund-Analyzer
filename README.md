# Mutual Fund Analyzer

A deployed Indian mutual-fund research application that turns a selection of **2–10 schemes** into an AI-assisted, ranked PDF report. It uses the live AMFI scheme master for discovery, retrieves historical NAV data, calculates financial metrics in Python, and uses an LLM to generate the executive summary and fund-wise ranking explanations.

**Live app:** https://mutual-fund-analyzer-rho.vercel.app  
**Backend health:** https://mutual-fund-analyzer-api-bqho.onrender.com/health

## What it does

### Multi-fund PDF report
- Search the live AMFI scheme master and select 2–10 schemes.
- Paste a custom list of scheme names (one per line, comma or semicolon separated).
- Choose a 1, 3, 5, or 10-year analysis period.
- Retrieve and validate historical NAV data for every selected scheme.
- Calculate total return, CAGR, annualized volatility, and maximum drawdown in Python.
- Rank the selected funds using a disclosed composite risk/return score and validated AI-assisted ordering.
- Generate an executive summary and evidence-based reason for each ranking position.
- Download a formatted A4 PDF with the comparison table, ranking, individual scheme details, data-quality notes, methodology, and disclaimer.

### AI assistant
The original single-fund conversational analysis remains available in the AI Assistant tab. It is separate from the multi-fund Ranked PDF Report workflow.

## Ranking methodology

Each metric is min-max normalized within the funds selected for that report:

| Metric | Weight | Preferred direction |
|---|---:|---|
| CAGR | 40% | Higher |
| Annualized volatility | 30% | Lower |
| Maximum drawdown | 30% | Shallower / less negative |

The application calculates the metrics and composite scores. The LLM receives those verified figures and scores, then returns the ranking and explanations. Its returned scheme order is validated to ensure every selected scheme appears exactly once. If the LLM is unavailable or returns an invalid ranking, the application falls back to the deterministic composite-score order.

Scores are **relative to the funds selected in a particular report**, not universal ratings or forecasts. Comparisons across different fund categories, investment mandates, geographies, or benchmarks may not be like-for-like. A higher historical score does not establish that a fund is suitable for an investor.

## Data sources and calculation policy

- **Scheme discovery / primary reference:** AMFI public scheme master.
- **Historical NAV source:** AMFI historical NAV archive where sufficient data is available.
- **Fallback historical NAV source:** MFapi.in, used when AMFI historical retrieval is unavailable or insufficient.
- All reported performance and risk metrics are calculated by this application from NAV observations; the LLM does not calculate or supply the financial figures.
- Invalid/non-positive NAVs are discarded; identical same-date observations are deduplicated; conflicting same-date NAVs are rejected.
- Volatility is the sample standard deviation of consecutive NAV returns annualized by √252.
- Maximum drawdown is the largest peak-to-subsequent-trough decline in the selected NAV series.
- The report includes observation counts, return-interval counts, calendar gaps, and whether the latest historical NAV reconciles with the current AMFI scheme-master NAV/date.
- Benchmark TRI data is not integrated in this version. Consequently, benchmark-relative alpha, beta, Sharpe ratio, information ratio, and market-capture ratios are not presented.

Historical NAV data availability and provider coverage can vary by scheme and period. A report is rejected rather than silently ranking an incomplete selection when a scheme cannot be resolved or does not have sufficient history.

## Architecture

- **Frontend:** Next.js 16, React 19, html2pdf.js; deployed on Vercel.
- **Backend:** Python, FastAPI; deployed on Render.
- **AI orchestration:** LangGraph.
- **LLM:** Groq, openai/gpt-oss-120b.
- **NAV ingestion:** AMFI with MFapi.in fallback.
- **CI:** GitHub Actions runs the backend test suite on relevant pushes and pull requests.

## API

### GET /health
Returns backend health status.

### GET /funds/search?q=<text>&limit=20
Searches the current AMFI scheme master. The response contains scheme name, scheme code, ISIN, plan/option, latest NAV, and NAV date.

### POST /compare
Example request using the three schemes exercised in the production demo:

~~~json
{
  "fund_names": [
    "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
    "HDFC Mid Cap Fund - Direct Plan - Growth Option",
    "ICICI Prudential US Bluechip Equity Fund - Direct Plan - Growth"
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
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
~~~

Create `backend/.env`:

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

Create `frontend/.env.local`:

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

GitHub Actions runs the NAV analytics and multi-fund comparison tests automatically when backend files or the workflow change. Check the Actions tab for the latest run status before submission.

## Deployment

- Frontend production project: Vercel, root directory `frontend`.
- Backend service: Render, start command `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Backend environment variable: `GROQ_API_KEY`.
- Frontend environment variable: `NEXT_PUBLIC_BACKEND_URL=https://mutual-fund-analyzer-api-bqho.onrender.com`.

Never commit API keys or local `.env` files.

## Take-home submission checklist

- [x] Production app and multi-fund report flow deployed.
- [x] Three-scheme, one-year production demo completed successfully on 16 November 2026.
- [ ] Download and inspect the final PDF; include that PDF as the sample deliverable in the submission.
- [ ] Record a short demo video (target: no more than five minutes).
- [ ] Include this repository URL and the live app URL in the submission.
- [ ] Include `docs/AI_SESSION_LOG.md` if the interviewer requests AI-tool activity logs.
- [ ] Record the actual time spent in the submission form; do not estimate or fabricate it.

A concise walkthrough is available in `docs/DEMO_SCRIPT.md`.

## Disclaimer

Past performance is not indicative of future returns. Mutual fund investments are subject to market risks. Read all scheme-related documents carefully. This tool is for informational research only and does not provide personalized investment advice.
