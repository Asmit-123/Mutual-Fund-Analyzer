import json
import re

from langchain_groq import ChatGroq
from graph.state import AgentState
from data_sources.mutual_fund_nav import get_fund_analytics, MarketDataError
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)


def extract_fund_names_from_query(query: str) -> list[str]:
    """Extract only scheme names explicitly mentioned by the user."""
    prompt = f"""
Extract Indian mutual fund scheme names explicitly mentioned in the user's request.
Return ONLY valid JSON in this exact shape: {{"fund_names": ["scheme name"]}}.
Do not guess, autocomplete, recommend, or invent fund names.
If no specific scheme is named, return an empty list.
User request: {json.dumps(query)}
"""
    response = llm.invoke(prompt)
    raw = response.content.strip()
    raw = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", raw, flags=re.IGNORECASE)
    try:
        parsed = json.loads(raw)
        names = parsed.get("fund_names", [])
        if not isinstance(names, list):
            return []
        return list(dict.fromkeys(
            name.strip() for name in names
            if isinstance(name, str) and name.strip()
        ))
    except (json.JSONDecodeError, AttributeError, TypeError):
        print(f"Could not parse fund-name extraction response: {raw}")
        return []


def fund_info_node(state: AgentState) -> dict:
    query = state["messages"][-1].content
    funds = state.get("fund_names") or []
    period = int(state.get("period") or 1)

    if not funds:
        funds = extract_fund_names_from_query(query)

    if not funds:
        msg = (
            "I couldn't identify a specific mutual fund scheme. Please include its "
            "scheme name, for example: 'Analyze Parag Parikh Flexi Cap Fund for 1 year.'"
        )
        return {"tool_result": msg, "tool_results": {"fund_info": msg}}

    analyses = []
    errors = []
    for fund in funds:
        try:
            analyses.append(get_fund_analytics(fund, period))
        except (MarketDataError, ValueError) as exc:
            errors.append({"fund": fund, "error": str(exc)})
        except Exception as exc:
            # Keep one provider/network failure from crashing the entire report.
            print(f"Unexpected NAV analytics error for {fund}: {type(exc).__name__}: {exc}")
            errors.append({
                "fund": fund,
                "error": f"Unexpected data retrieval error ({type(exc).__name__}).",
            })

    evidence = {"successful_analyses": analyses, "unavailable_funds": errors}
    data_dump = json.dumps(evidence, indent=2)

    if not analyses:
        report = (
            "I couldn't retrieve enough historical NAV data to analyze the requested "
            "scheme(s). No performance figures have been estimated or invented.\n\n"
            f"Diagnostics:\n{data_dump}"
        )
        return {"tool_result": report, "tool_results": {"fund_info": report}}

    prompt = f"""
You are an evidence-based Indian mutual fund research analyst.

User request: {json.dumps(query)}
Requested period: {period} year(s).
Verified data retrieved for this request:
{data_dump}

Write a clear report using ONLY the supplied data. Preserve all numeric values exactly.
For each available scheme include:
- Scheme name, plan/option, scheme code and ISIN when available.
- NAV start/end dates and NAV values.
- Total return, CAGR, annualized volatility and maximum drawdown.
- Number of unique NAV observations AND number of periodic return intervals (these
  counts differ by one for a continuous series).
- Data source and the supplied data-quality checks: invalid rows discarded,
  duplicate rows removed, largest calendar gap, and whether the latest historical
  NAV matches the current AMFI scheme-master NAV/date when that check is available.
- State the volatility annualization factor and method (sample standard deviation
  of consecutive NAV returns multiplied by sqrt(252)).
- State the maximum-drawdown method (largest decline from a running NAV peak).
- If the latest historical NAV does not match the current scheme-master NAV/date,
  clearly flag the mismatch as a data freshness/reconciliation warning; do not
  silently claim that the series is fully reconciled.
Explain metrics accurately using these definitions:
- Growth option: the return is calculated from the NAV change. Income and gains
  remain invested in the scheme and are reflected in its NAV; do not describe
  Growth-option returns as excluding the fund's underlying income or gains.
- Annualized volatility: the dispersion/variability of periodic NAV returns,
  annualized using the supplied calculation. Do not describe it as a guaranteed
  or typical +/- range around an average return.
- Maximum drawdown: the largest peak-to-trough percentage decline in the
  observed NAV series during the selected period.
- Observation count: the number of unique NAV dates included in the selected
  calculation window, not the number of return intervals. The periodic return
  count is normally one less than the observation count.
State that historical returns are not guarantees.
If a fund failed, explain that its data was unavailable; do not fill gaps with estimates.

IMPORTANT DATA LIMITATION:
Market capture ratios (up/down capture) are NOT calculated in this version because
a validated benchmark total-return-index time series has not yet been integrated.
Do not invent or infer market capture ratios, benchmark-relative rankings, Sharpe ratios,
alpha, beta, or any other metric absent from the supplied data.
For multiple funds, compare only the supplied NAV-derived metrics and clearly note
that differences in category/benchmark may make a direct ranking inappropriate.
Identify AMFI as the primary NAV source. If the supplied data_source is MFapi.in,
identify it as the fallback source, not as an official AMFI API.
Explain that calculations are performed by this application from NAV history.
This is informational research, not personalized investment advice.
"""
    response = llm.invoke(prompt)
    final_result = response.content

    return {
        "tool_result": final_result,
        "tool_results": {"fund_info": final_result},
    }
