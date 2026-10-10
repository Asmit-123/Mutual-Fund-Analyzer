import requests
import json
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from graph.state import AgentState
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

llm = ChatOpenAI(model="gpt-4o", temperature=0.2)

def fetch_advisorkhoj_capture_ratio(fund_name: str, period_years: int) -> dict:
    print(f"fetch_advisorkhoj_capture_ratio for {fund_name}, period: {period_years}")
    
    url = "https://www.advisorkhoj.com/mutual-funds-research/market-capture-ratio"
    
    payload = {
        "scheme_name": fund_name,
        "period": str(period_years) 
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Locate the cells containing the specific text and grab the adjacent value
        up_td = soup.find('td', text=lambda t: t and 'Up Market Capture Ratio' in t)
        down_td = soup.find('td', text=lambda t: t and 'Down Market Capture Ratio' in t)
        
        # Find 'Capture Ratio' but exclude the Up/Down variants to get the overall ratio
        overall_td = soup.find('td', text=lambda t: t and 'Capture Ratio' in t and 'Up' not in t and 'Down' not in t)

        up_capture = up_td.find_next_sibling('td').text.strip() if up_td else "N/A"
        down_capture = down_td.find_next_sibling('td').text.strip() if down_td else "N/A"
        overall_capture = overall_td.find_next_sibling('td').text.strip() if overall_td else "N/A"

        return {
            "fund": fund_name,
            "period": f"{period_years} Years",
            "up_market_capture": up_capture,
            "down_market_capture": down_capture,
            "overall_capture": overall_capture,
            "source": "AdvisorKhoj"
        }
    except Exception as e:
        print(f"Failed to fetch data for {fund_name}: {str(e)}")
        return {
            "fund": fund_name,
            "error": "Could not retrieve data from AdvisorKhoj"
        }

def fund_info_node(state: AgentState) -> dict:
    funds = state.get("fund_names", [])
    period = state.get("period", 1) # Default to 1 if not set in state
    
    if not funds:
        msg = "No specific fund names provided. Could not fetch fund info."
        return {
            "tool_result":  msg,
            "tool_results": {"fund_info": msg},
        }

    prev_results = state.get("tool_results", {})
    context_str = ""
    if state.get("has_sequential") and prev_results:
        filtered = {k: v for k, v in prev_results.items() if k != "fund_info"}
        if filtered:
            context_str = f"Context from previous tools:\n{filtered}\n\n"

    # Fetch AdvisorKhoj data for every chosen fund
    extracted_data = []
    for fund in funds:
        data = fetch_advisorkhoj_capture_ratio(fund, period)
        print(f"Data for {fund}:", data)
        extracted_data.append(data)

    data_dump = json.dumps(extracted_data, indent=2)
    query = state["messages"][-1].content

    # Updated prompt to specifically rank based on the scraped data as required
    PROMPT = f"""
    {context_str}
    You are an expert mutual fund analyst.
    The user asked: "{query}"

    Here is the Market Capture Ratio data scraped from AdvisorKhoj for a period of {period} years:
    {data_dump}

    Your job:
    1. Summarize and rank the funds based strictly on the provided AdvisorKhoj Market Capture Ratio data.
    2. Provide a specific reason for each fund's rank based on its Up-Market and Down-Market capture performance. (Context: A scheme that outperforms in both up markets and down markets is likely to give superior risk-adjusted returns).
    3. Include an overall summary at the end.
    4. If multiple funds were fetched, use a well-designed table or clear bullet points for easy reading.
    5. Do not use outside data or make up numbers. If a fund returned "N/A" or an error, state that the data could not be retrieved from AdvisorKhoj.
    """
    
    response = llm.invoke(PROMPT)
    final_result = response.content

    return {
        "tool_result":  final_result,
        "tool_results": {"fund_info": final_result},
    }