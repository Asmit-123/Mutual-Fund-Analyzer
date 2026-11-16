import re
from langchain_groq import ChatGroq
from graph.state import AgentState
from dotenv import load_dotenv

load_dotenv()

# Groq retired llama-3.3-70b-versatile on 2026-08-16.
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)

REPORT_DISCLAIMER = (
    "Disclaimer: Past performance is not indicative of future returns. "
    "This report is generated from mutual-fund NAV data and is for "
    "informational purposes only, not personalized investment advice."
)

SYNTH_PROMPT = """
You are a professional financial report designer and formatter.
Convert the supplied mutual-fund analysis into a polished, executive-ready
HTML document suitable for PDF generation.

Rules:
- Return ONLY valid HTML. Do not use Markdown, code fences, or conversational filler.
- Use semantic HTML and inline CSS for a clean, accessible, professional layout.
- Use a clear report title and organize the supplied analysis with useful headings,
  concise paragraphs, tables, and bullet points where appropriate.
- Adapt the structure to the information actually supplied. This may be a single
  fund analysis, not a multi-fund ranking.
- Do not create fund rankings, market-capture tables, up/down capture ratios,
  benchmark comparisons, or other sections unless the input explicitly contains
  validated data for them.
- Do NOT invent, estimate, infer, or fill in missing financial figures.
- Preserve the supplied fund name, plan/option, dates, NAV values, return figures,
  and data-source details accurately.
- If a metric or benchmark comparison is unavailable, state that it was not
  calculated/provided rather than fabricating a value.
- Do not mention AdvisorKhoj or claim that the report uses AdvisorKhoj data.
- Do not add your own disclaimer. The application will append the approved
  disclaimer after generating the report.
"""

def clean_html_output(text: str) -> str:
    """Clean model output and append the application's fixed disclaimer."""
    text = text.strip()
    text = re.sub(r"^\x60{3}(?:html)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\x60{3}$", "", text)

    # Remove model-generated disclaimer paragraphs so the report has one
    # consistent, application-controlled disclaimer.
    text = re.sub(
        r"<p\b[^>]*>.*?(?:AdvisorKhoj|Disclaimer\s*:).*?</p>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Guard against an obsolete source claim appearing outside a paragraph.
    text = re.sub(r"AdvisorKhoj", "the previous third-party source", text, flags=re.IGNORECASE)

    disclaimer_html = (
        '<p class="report-disclaimer" '
        'style="font-size:9px;color:#666;font-style:italic;'
        'margin-top:28px;border-top:1px solid #ddd;padding-top:10px;">'
        + REPORT_DISCLAIMER
        + "</p>"
    )

    if re.search(r"</body\s*>", text, flags=re.IGNORECASE):
        text = re.sub(
            r"</body\s*>",
            disclaimer_html + "</body>",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        text += disclaimer_html

    return text.strip()


def synthesizer_node(state: AgentState) -> dict:
    print("Executing synthesizer_node to build final PDF report...")

    tool_results = state.get("tool_results", {})
    raw_report_data = tool_results.get("fund_info")

    if not raw_report_data:
        fallback = (
            "<p>Error: No fund data could be retrieved or analyzed. "
            "Please check your inputs and try again.</p>"
        )
        return {"tool_result": fallback}

    instruction = (
        "Format the following mutual-fund analysis into the final HTML report. "
        "Preserve all supplied financial values and dates exactly.\n\n"
        f"{raw_report_data}"
    )

    response = llm.invoke(
        [
            ("system", SYNTH_PROMPT),
            ("human", instruction),
        ]
    )

    cleaned_html = clean_html_output(response.content)
    return {"tool_result": cleaned_html}
