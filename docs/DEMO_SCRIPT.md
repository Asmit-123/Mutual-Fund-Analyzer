# Five-minute demo script

Target duration: approximately 4 minutes 30 seconds.

## 0:00–0:25 — Introduce the app
Open the production URL: https://mutual-fund-analyzer-rho.vercel.app. Explain that the application turns a selection of 2–10 Indian mutual-fund schemes into a NAV-backed comparison and downloadable AI-assisted PDF report.

## 0:25–1:15 — Search and select funds
Open the **Ranked PDF Report** tab. Use the live AMFI scheme search and select:
- Parag Parikh Flexi Cap Fund – Direct Plan – Growth.
- HDFC Mid Cap Fund – Direct Plan – Growth Option.
- ICICI Prudential US Bluechip Equity Fund – Direct Plan – Growth.

Point out the scheme code and latest NAV/date shown in the search suggestions. Explain that the suggestions come from the live scheme master, not a hard-coded fund catalogue.

## 1:15–1:35 — Set the analysis period
Keep the analysis period at **1Y** for this demo. Mention that 1Y, 3Y, 5Y, and 10Y are supported. The paste-list field is an alternative input method; it is not necessary when selecting funds from search.

## 1:35–2:25 — Generate the report
Click **Generate ranked report for 3 funds**. Explain that the backend retrieves the NAV history for every selected scheme, validates the observations, calculates performance and risk metrics, and rejects an incomplete comparison rather than silently ranking only the funds that succeeded.

## 2:25–3:35 — Review the result
Show the executive summary, AI-assisted ranking, side-by-side comparison, and individual scheme details. Explain the composite weighting:
- CAGR: 40%.
- Annualized volatility: 30%.
- Maximum drawdown: 30%.

Clarify that the LLM explains and proposes the ordering using application-calculated metrics, and the returned scheme list is validated. Scores are relative to the selected set. These three funds span different investment categories/geographies, so this is a workflow demonstration, not a like-for-like investment recommendation.

## 3:35–4:15 — Download the PDF
Click **Download PDF**. Open the downloaded file and show the report title, ranking, comparison table, one fund's NAV/data-quality details, methodology, and disclaimer. Check that tables and headings are not clipped across page breaks.

## 4:15–4:30 — Close
Summarize the data flow: AMFI scheme master and NAV history where available, MFapi.in historical NAV fallback, Python-based financial calculations, and LangGraph/Groq for AI-assisted narrative and ranking. Mention that benchmark TRI metrics are not claimed because benchmark TRI integration is not included.
