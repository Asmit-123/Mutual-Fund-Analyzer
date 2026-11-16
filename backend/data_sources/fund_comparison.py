"""Multi-fund comparison and evidence-based AI report generation."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from data_sources.mutual_fund_nav import (
    MarketDataError,
    _fetch_amfi_scheme_master,
    _normalize_name,
    get_fund_analytics,
)
import requests


def search_schemes(query: str, limit: int = 20) -> list[dict[str, str]]:
    """Search the live AMFI scheme master; never return synthetic fund names."""
    normalized = _normalize_name(query)
    if len(normalized) < 2:
        return []
    tokens = normalized.split()
    with requests.Session() as session:
        schemes = _fetch_amfi_scheme_master(session)
    matches = []
    for scheme in schemes:
        display_name = " - ".join(
            part.strip() for part in (
                scheme.get("scheme_name", ""),
                scheme.get("plan", ""),
                scheme.get("option", ""),
            ) if part and part.strip()
        )
        name = _normalize_name(display_name)
        if all(token in name for token in tokens):
            matches.append({
                "scheme_name": display_name,
                "scheme_code": scheme["scheme_code"],
                "isin": scheme.get("isin", ""),
                "plan": scheme.get("plan", ""),
                "option": scheme.get("option", ""),
                "latest_nav": scheme.get("latest_nav", ""),
                "latest_date": scheme.get("latest_date", ""),
            })
    # Prefer Direct Growth when the search is broad, while retaining other
    # variants so the user can explicitly choose the exact scheme.
    matches.sort(key=lambda item: (
        "direct" not in (item["plan"] + " " + item["scheme_name"]).lower(),
        "growth" not in (item["option"] + " " + item["scheme_name"]).lower(),
        item["scheme_name"].lower(),
    ))
    return matches[: max(1, min(limit, 50))]


def _normalize_metric(values: list[float], higher_is_better: bool) -> list[float]:
    low, high = min(values), max(values)
    if abs(high - low) < 1e-12:
        return [50.0] * len(values)
    scores = [(value - low) / (high - low) * 100 for value in values]
    return scores if higher_is_better else [100 - score for score in scores]


def rank_funds(analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transparent composite score: CAGR 40%, volatility 30%, drawdown 30%.

    Scores are relative only to the funds in this report. They are not ratings,
    forecasts, or a substitute for category/benchmark-aware analysis.
    """
    if not analyses:
        return []
    cagr = [float(item["cagr_pct"]) for item in analyses]
    volatility = [
        float(item["annualized_volatility_pct"])
        if item.get("annualized_volatility_pct") is not None else 0.0
        for item in analyses
    ]
    drawdown = [float(item["max_drawdown_pct"]) for item in analyses]
    cagr_score = _normalize_metric(cagr, True)
    volatility_score = _normalize_metric(volatility, False)
    drawdown_score = _normalize_metric(drawdown, True)

    ranked = []
    for index, item in enumerate(analyses):
        score = (
            0.40 * cagr_score[index]
            + 0.30 * volatility_score[index]
            + 0.30 * drawdown_score[index]
        )
        ranked.append({
            **item,
            "comparison_score": round(score, 2),
            "score_components": {
                "cagr_score": round(cagr_score[index], 2),
                "volatility_score": round(volatility_score[index], 2),
                "drawdown_score": round(drawdown_score[index], 2),
            },
        })
    ranked.sort(
        key=lambda item: (
            item["comparison_score"],
            item["cagr_pct"],
            item["max_drawdown_pct"],
        ),
        reverse=True,
    )
    for position, item in enumerate(ranked, start=1):
        item["rank"] = position
    return ranked


def _fallback_reason(item: dict[str, Any]) -> str:
    return (
        f"Ranked #{item['rank']} with a composite score of {item['comparison_score']}/100. "
        f"It returned {item['cagr_pct']:.2f}% CAGR, with {item['annualized_volatility_pct']}"
        f"% annualized volatility and {item['max_drawdown_pct']:.2f}% maximum drawdown. "
        "The score weights return (40%), volatility (30%) and drawdown (30%) equally "
        "within this selected comparison set."
    )


def compare_funds(fund_names: list[str], period_years: int) -> dict[str, Any]:
    """Fetch 2–10 live fund histories, rank comparable metrics, and write an AI brief."""
    if period_years not in (1, 3, 5, 10):
        raise ValueError("Supported periods are 1, 3, 5, and 10 years.")
    cleaned = list(dict.fromkeys(
        name.strip() for name in fund_names
        if isinstance(name, str) and name.strip()
    ))
    if not 2 <= len(cleaned) <= 10:
        raise ValueError("Choose between 2 and 10 distinct mutual funds.")

    analyses: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(5, len(cleaned))) as executor:
        futures = {
            executor.submit(get_fund_analytics, name, period_years): name
            for name in cleaned
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                analyses.append(future.result())
            except Exception as exc:
                errors.append({"fund": name, "error": str(exc)})

    if errors:
        detail = "; ".join(f"{item['fund']}: {item['error']}" for item in errors)
        raise MarketDataError(
            "A complete like-for-like report could not be produced. "
            "Correct or remove the unavailable scheme(s) and try again. " + detail
        )
    if len(analyses) != len(cleaned):
        raise MarketDataError("Not all selected funds returned valid NAV histories.")

    ranked = rank_funds(analyses)
    evidence = [{
        "rank": item["rank"],
        "scheme_name": item["scheme_name"],
        "scheme_code": item["scheme_code"],
        "cagr_pct": item["cagr_pct"],
        "total_return_pct": item["total_return_pct"],
        "annualized_volatility_pct": item["annualized_volatility_pct"],
        "max_drawdown_pct": item["max_drawdown_pct"],
        "comparison_score": item["comparison_score"],
        "score_components": item["score_components"],
    } for item in ranked]

    prompt = f"""
You are writing a concise, evidence-based Indian mutual-fund comparison report.
Use the supplied composite scores and underlying NAV metrics to make an overall
risk/return ranking. The score is a quantitative anchor, but consider the complete
trade-off rather than treating any single metric as decisive. Return every scheme
exactly once, with the strongest overall profile first. Do not invent metrics.

Period: {period_years} year(s)
Ranking method: composite score = CAGR 40% + lower annualized volatility 30%
+ shallower maximum drawdown 30%. Scores are min-max normalized within this
selected set and are relative comparison aids, not universal ratings.
Verified data:
{json.dumps(evidence, indent=2)}

Return ONLY valid JSON with this exact shape:
{{
  "executive_summary": "2-4 sentences summarising the actual comparison.",
  "ranking": [
    {{"scheme_code": "exact code", "reason": "1-3 sentences grounded only in its supplied metrics"}}
  ],
  "limitations": "Mention that fund categories and benchmarks may differ, that the score is relative to this selected set, and that NAV-only data does not establish future suitability."
}}
Do not claim a fund is best for every investor. Do not invent category, benchmark,
alpha, beta, Sharpe ratio, capture ratio, manager commentary, or market events.
Mention trade-offs: a higher return can come with higher volatility or drawdown.
"""
    ai_summary = ""
    try:
        from graph.nodes.fund_info import llm
        response = llm.invoke(prompt)
        raw = response.content.strip()
        raw = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", raw, flags=re.I)
        parsed = json.loads(raw)
        ai_summary = str(parsed.get("executive_summary", "")).strip()
        ai_ranking = parsed.get("ranking", [])
        ai_codes = [
            str(item.get("scheme_code"))
            for item in ai_ranking
            if isinstance(item, dict) and item.get("scheme_code") is not None
        ]
        expected_codes = {str(item["scheme_code"]) for item in ranked}
        if len(ai_codes) == len(ranked) and len(set(ai_codes)) == len(ranked) and set(ai_codes) == expected_codes:
            by_code = {str(item["scheme_code"]): item for item in ranked}
            ranked = [by_code[code] for code in ai_codes]
            for position, item in enumerate(ranked, start=1):
                item["rank"] = position
                item["ranking_reason"] = next(
                    str(entry.get("reason", "")).strip()
                    for entry in ai_ranking
                    if str(entry.get("scheme_code")) == str(item["scheme_code"])
                )
            ranking_source = "LLM ranking validated against supplied scheme codes and NAV metrics"
        else:
            ranking_source = "Deterministic composite-score fallback (LLM ranking response was invalid)"
        if not ai_summary:
            ai_summary = "The ranking is based on the disclosed return and risk metrics."
    except Exception as exc:
        # Keep a useful, deterministic report available if the LLM is down or
        # returns malformed JSON. Financial figures never depend on the LLM.
        ranking_source = "Deterministic composite-score fallback (AI unavailable)"
        print(f"AI comparison narrative unavailable: {type(exc).__name__}: {exc}")
        ai_summary = (
            "The funds are ranked using the disclosed composite score. Review the "
            "individual return and risk measures alongside the ranking."
        )

    for item in ranked:
        if not item.get("ranking_reason"):
            item["ranking_reason"] = _fallback_reason(item)

    return {
        "period_years": period_years,
        "generated_at_utc": ranked[0]["data_retrieved_at_utc"],
        "fund_count": len(ranked),
        "executive_summary": ai_summary,
        "limitations": (
            "The composite score is relative to the selected funds only. Fund categories "
            "and benchmarks may differ, and NAV-only metrics do not establish future "
            "suitability. No validated benchmark TRI is integrated in this version."
        ),
        "ranking_source": ranking_source,
        "ranking_method": {
            "name": "LLM-assisted relative risk-return ranking",
            "weights": {"CAGR": 0.40, "annualized_volatility": 0.30, "maximum_drawdown": 0.30},
            "description": (
                "Min-max normalized within this report: higher CAGR scores better; "
                "lower volatility and a shallower (less negative) drawdown score better."
            ),
        },
        "ranked_funds": ranked,
        "data_source_note": (
            "AMFI is the primary NAV source. MFapi.in is used as a fallback when AMFI "
            "historical NAV retrieval is insufficient. Metrics are calculated by this app."
        ),
    }
