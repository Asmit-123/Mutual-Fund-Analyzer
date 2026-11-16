# AI Coding Session Log

This file records high-level task prompts and implementation work relevant to the project. It is a concise activity log, not a private reasoning transcript.

## Session: Multi-fund report implementation and production demo

**User task:** Complete a mutual-fund research application that accepts multiple schemes, analyzes a selected historical period, ranks the schemes with AI-assisted explanations, and generates a downloadable PDF.

**Implementation goals:**
1. Add live scheme search using AMFI's current scheme master.
2. Let users select 2–10 schemes through search or paste a list.
3. Support 1, 3, 5, and 10-year periods.
4. Retrieve and validate NAV histories for every selected fund.
5. Calculate comparable return and risk metrics and disclose the ranking methodology.
6. Use an LLM to produce an executive summary, ranking order, and evidence-based ranking explanations.
7. Generate a formatted downloadable PDF.
8. Document setup, API behavior, data limitations, and automated tests.

**Changes made:**
- Added `backend/data_sources/fund_comparison.py` with live AMFI scheme search, parallel NAV retrieval, comparison calculations, composite scoring, and LLM-assisted report narrative/ranking.
- Added `GET /funds/search` and `POST /compare` API endpoints.
- Added `backend/tests/test_fund_comparison.py` for comparison scoring and ranking behavior.
- Built a two-mode frontend: Ranked PDF Report and the existing AI Assistant.
- Added live search suggestions, selected-fund chips, paste-list input, period selection, side-by-side metrics, individual fund data-quality details, and A4 PDF export.
- Added or updated backend CI to run the full backend test suite on relevant changes.
- Updated the README, demo walkthrough, and this activity log.

**Ranking design:** CAGR 40%, annualized volatility 30%, and maximum drawdown 30%, min-max normalized within the selected comparison set. The application calculates the metrics and composite scores. The LLM receives those values and returns an ordering with explanations. The returned ordering is validated so each selected scheme appears exactly once; an invalid or unavailable LLM ranking falls back to deterministic composite-score order.

**Data integrity guardrails:** A report is rejected if any selected scheme cannot be resolved or lacks sufficient NAV history. The application does not silently omit unavailable funds or fabricate missing figures. Benchmark TRI metrics are explicitly disclosed as unavailable.

## Production demo completed

On 16 November 2026, the production Ranked PDF Report workflow successfully generated a one-year comparison for these three AMFI schemes:

1. Parag Parikh Flexi Cap Fund – Direct Plan – Growth.
2. HDFC Mid Cap Fund – Direct Plan – Growth Option.
3. ICICI Prudential US Bluechip Equity Fund – Direct Plan – Growth.

The user confirmed that the report contained NAV-derived returns, CAGR, annualized volatility, maximum drawdown, composite scores, an LLM-assisted ranking, individual scheme details, and data-quality disclosures. The sample PDF still needs to be downloaded and visually inspected before it is attached to the final submission.

**Known limitations:** Benchmark TRI integration is not present. The report's normalized scores are relative to the selected schemes and can be misleading as a universal comparison when categories, geographies, or mandates differ. Historical performance is not predictive of future returns.

**Pre-submission checks:** Confirm the latest GitHub Actions run is green, verify the live frontend and backend health endpoint, download and inspect the PDF, and record the short demo video. A successful report generation is evidence of the demonstrated end-to-end flow, but it does not replace a visual PDF review or CI verification.
