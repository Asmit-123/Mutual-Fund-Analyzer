import json
import re
import requests
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq
from graph.state import AgentState
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Use a supported Groq-hosted model for extracting fund names from natural language
# and for explaining the live AdvisorKhoj data.
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)


def extract_fund_names_from_query(query: str) -> list[str]:
    """Extract only fund names explicitly mentioned by the user; never invent a scheme."""
    prompt = f"""
Extract Indian mutual fund scheme names explicitly mentioned in the user's request.
Return ONLY valid JSON in this exact shape: {{"fund_names": ["scheme name"]}}.
Rules:
- Include every explicitly named mutual fund scheme, preserving its wording.
- Do not guess, autocomplete, recommend, or invent fund names.
- If no specific scheme is named, return an empty list.
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


def fetch_advisorkhoj_capture_ratio(fund_name: str, period_years: int) -> dict:
    """Fetch the requested scheme's current market-capture data from AdvisorKhoj at request time."""
    print(f"Fetching live AdvisorKhoj capture data for {fund_name}, period: {period_years}")

    url = "https://www.advisorkhoj.com/mutual-funds-research/market-capture-ratio"
    payload = {"scheme_name": fund_name, "period": str(period_years)}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        response = requests.post(url, data=payload, headers=headers, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        def value_for_label(predicate):
            label = soup.find("td", string=predicate)
            if not label:
                return "N/A"
            value_cell = label.find_next_sibling("td")
            return value_cell.get_text(" ", strip=True) if value_cell else "N/A"

        up_capture = value_for_label(
            lambda text: bool(text and "Up Market Capture Ratio" in text)
        )
        down_capture = value_for_label(
            lambda text: bool(text and "Down Market Capture Ratio" in text)
        )
        overall_capture = value_for_label(
            lambda text: bool(
                text and "Capture Ratio" in text
                and "Up" not in text and "Down" not in text
            )
        )

        return {
            "fund": fund_name,
            "period": f"{period_years} year(s)",
            "up_market_capture": up_capture,
            "down_market_capture": down_capture,
            "overall_capture": overall_capture,
            "source": "AdvisorKhoj (fetched live for this request)",
            "retrieved": True,
        }
    except requests.RequestException as exc:
        print(f"AdvisorKhoj request failed for {fund_name}: {exc}")
        return {
            "fund": fund_name,
            "period": f"{period_years} year(s)",
            "error": f"AdvisorKhoj request failed: {type(exc).__name__}",
            "source": "AdvisorKhoj",
            "retrieved": False,
        }


def fund_info_node(state: AgentState) -> dict:
    query = state["messages"][-1].content
    funds = state.get("fund_names") or []
    period = state.get("period") or 1

    # The website sends the natural-language query and selected period. Resolve
    # fund names here so the UI does not need a hard-coded scheme catalogue.
    if not funds:
        funds = extract_fund_names_from_query(query)

    if not funds:
        msg = (
            "I couldn't identify a specific mutual fund scheme in your request. "
            "Please include the complete scheme name, for example: "
            "'Analyze Parag Parikh Flexi Cap Fund for 1 year.'"
        )
        return {"tool_result": msg, "tool_results": {"fund_info": msg}}

    extracted_data = [
        fetch_advisorkhoj_capture_ratio(fund, int(period))
        for fund in funds
    ]

    data_dump = json.dumps(extracted_data, indent=2)
    successful = [
        item for item in extracted_data
        if item.get("retrieved")
        and any(
            item.get(key) not in (None, "", "N/A")
            for key in ("up_market_capture", "down_market_capture", "overall_capture")
        )
    ]

    if not successful:
        report = (
            "AdvisorKhoj did not return usable market capture ratio values for the "
            f"requested scheme(s): {', '.join(funds)}. No rankings or ratios have "
            "been generated because the live source did not provide sufficient data. "
            "Please verify the exact scheme name or try another reporting period.\n\n"
            f"Source response:\n{data_dump}"
        )
        return {"tool_result": report, "tool_results": {"fund_info": report}}

    prompt = f"""
You are an evidence-based Indian mutual fund analyst.

The user asked: {json.dumps(query)}
Requested reporting period: {period} year(s).
The following data was fetched live from AdvisorKhoj for this request:
{data_dump}

Prepare a concise ranking and analysis using ONLY the supplied values.
Requirements:
1. Include each requested fund and its Up, Down, and Overall Market Capture Ratios.
2. Rank funds only when usable numeric data supports a comparison. If only one fund is supplied, present it as an individual analysis, not a competitive ranking.
3. Explain that lower down-capture can indicate better downside resilience, while higher up-capture indicates stronger participation in rising markets. Do not treat either metric alone as a guaranteed measure of future returns.
4. Never invent missing values, fund details, returns, or rankings. Mark unavailable values as N/A.
5. Clearly identify AdvisorKhoj as the data source and state that values were fetched for this request.
6. If a scheme has an error or all values are N/A, explicitly say so.
7. This is informational analysis, not personalized investment advice.
"""
    response = llm.invoke(prompt)
    final_result = response.content

    return {
        "tool_result": final_result,
        "tool_results": {"fund_info": final_result},
    }
