"""Provider-agnostic Indian mutual-fund NAV ingestion and analytics.

Primary source: AMFI's public NAV feeds and historical NAV archive.
Fallback: MFapi.in JSON mirror when AMFI history is unavailable.
The analytics layer consumes normalized NAV observations, not provider HTML.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
import math
import re

import requests

AMFI_LATEST_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
AMFI_HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
MFAPI_HISTORY_URL = "https://api.mfapi.in/mf/{scheme_code}"
TIMEOUT = 35
HEADERS = {"User-Agent": "MutualFundAnalyzer/1.0 (research; contact: project-maintainer)"}


class MarketDataError(RuntimeError):
    """Raised when no provider can supply valid NAV history."""


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _fetch_amfi_scheme_master(session: requests.Session) -> list[dict[str, str]]:
    response = session.get(AMFI_LATEST_URL, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    schemes: list[dict[str, str]] = []
    for line in response.text.splitlines():
        fields = [part.strip() for part in line.split(";")]
        # Current AMFI NAVAll feed has 8 fields; older rows can have 6.
        if len(fields) >= 8 and fields[0].isdigit():
            code, isin1, isin2, name, plan, option, nav, nav_date = fields[:8]
        elif len(fields) >= 6 and fields[0].isdigit():
            code, isin1, isin2, name, nav, nav_date = fields[:6]
            plan, option = "", ""
        else:
            continue
        if not name or not re.fullmatch(r"\d+(?:\.\d+)?", nav):
            continue
        schemes.append({
            "scheme_code": code, "isin": isin1 or isin2, "scheme_name": name,
            "plan": plan, "option": option, "latest_nav": nav, "latest_date": nav_date,
        })
    return schemes


def _resolve_scheme(schemes: list[dict[str, str]], requested_name: str) -> dict[str, str]:
    needle = re.sub(r"[^a-z0-9]+", " ", requested_name.lower()).strip()
    matches = [
        item for item in schemes
        if needle in re.sub(r"[^a-z0-9]+", " ", item["scheme_name"].lower()).strip()
    ]
    if not matches:
        # Allow an exact normalized name match in either direction, but do not
        # silently choose an unrelated fund.
        tokens = set(needle.split())
        matches = [
            item for item in schemes
            if tokens and tokens.issubset(
                set(re.sub(r"[^a-z0-9]+", " ", item["scheme_name"].lower()).split())
            )
        ]
    if not matches:
        raise MarketDataError(f"No matching scheme found in AMFI's current scheme feed for '{requested_name}'.")

    def preference(item: dict[str, str]) -> tuple[int, int, int]:
        plan = item["plan"].lower()
        option = item["option"].lower()
        return (
            1 if "direct" in plan else 0,
            1 if "growth" in option else 0,
            1 if item["scheme_name"].lower() == requested_name.lower() else 0,
        )
    growth = [item for item in matches if "growth" in item["option"].lower()]
    return sorted(growth or matches, key=preference, reverse=True)[0]


def _amfi_history_chunk(
    session: requests.Session, scheme_code: str, start: date, end: date
) -> list[dict[str, Any]]:
    params = {
        "tp": "1",
        "frmdt": start.strftime("%d-%b-%Y"),
        "todt": end.strftime("%d-%b-%Y"),
    }
    response = session.get(AMFI_HISTORY_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    observations: list[dict[str, Any]] = []
    for line in response.text.splitlines():
        fields = [part.strip() for part in line.split(";")]
        if len(fields) < 6 or fields[0] != scheme_code:
            continue
        # AMFI historical archive schema: code;name;ISIN1;ISIN2;NAV;repurchase;sale;date.
        # Also tolerate the 6-column variant used by older exports.
        nav_candidates = fields[4:-1]
        nav = next((v for v in nav_candidates if re.fullmatch(r"\d+(?:\.\d+)?", v)), None)
        nav_date = _parse_date(fields[-1])
        if nav and nav_date:
            observations.append({"date": nav_date, "nav": float(nav), "source": "AMFI"})
    return observations


def _fetch_amfi_history(
    session: requests.Session, scheme_code: str, period_years: int
) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=round(period_years * 365.25) + 10)
    observations: list[dict[str, Any]] = []
    # Keep each request to a 90-day window to respect AMFI's public NAV-history
    # interface limit and avoid downloading an unnecessarily large archive.
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=89), end)
        observations.extend(_amfi_history_chunk(session, scheme_code, cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    unique = {item["date"]: item for item in observations}
    return sorted(unique.values(), key=lambda item: item["date"])


def _fetch_mfapi_history(
    session: requests.Session, scheme_code: str
) -> list[dict[str, Any]]:
    response = session.get(
        MFAPI_HISTORY_URL.format(scheme_code=scheme_code),
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    raw_data = payload.get("data", [])
    observations = []
    for row in raw_data:
        nav_date = _parse_date(str(row.get("date", "")))
        try:
            nav = float(row.get("nav"))
        except (TypeError, ValueError):
            continue
        if nav_date and nav > 0:
            observations.append({"date": nav_date, "nav": nav, "source": "MFapi.in"})
    return sorted(observations, key=lambda item: item["date"])


def _anniversary_date(as_of: date, years: int) -> date:
    """Subtract calendar years, handling leap-day anniversaries safely."""
    try:
        return as_of.replace(year=as_of.year - years)
    except ValueError:
        # Feb 29 -> Feb 28 in a non-leap target year.
        return as_of.replace(year=as_of.year - years, day=28)


def _calculate_metrics(
    observations: list[dict[str, Any]], period_years: int
) -> dict[str, Any]:
    # Count one observation per calendar date. Some upstream mirrors can
    # return duplicate rows; retain the last valid row for each date.
    by_date: dict[date, dict[str, Any]] = {}
    for item in observations:
        try:
            nav_value = float(item.get("nav", 0))
        except (TypeError, ValueError):
            continue
        if nav_value > 0:
            by_date[item["date"]] = {**item, "nav": nav_value}
    ordered = [by_date[day] for day in sorted(by_date)]
    if len(ordered) < 2:
        raise MarketDataError("Insufficient valid NAV observations.")

    # Anchor the requested window to the latest NAV actually available, not
    # the server's current date. For weekends/holidays, use the last NAV on or
    # before the calendar anniversary (never the next trading day's NAV).
    last = ordered[-1]
    anniversary = _anniversary_date(last["date"], period_years)
    eligible_starts = [i for i, item in enumerate(ordered) if item["date"] <= anniversary]
    if not eligible_starts:
        raise MarketDataError(
            f"NAV history does not reach the {period_years}-year anniversary "
            f"({anniversary.isoformat()})."
        )
    start_index = eligible_starts[-1]
    points = ordered[start_index:]
    if len(points) < 2:
        raise MarketDataError(
            f"Only {len(points)} NAV observation(s) were available for the requested period."
        )
    first = points[0]
    elapsed_days = (last["date"] - first["date"]).days
    if elapsed_days <= 0:
        raise MarketDataError("NAV history does not cover a positive time interval.")

    total_return = (last["nav"] / first["nav"] - 1.0) * 100
    cagr = ((last["nav"] / first["nav"]) ** (365.25 / elapsed_days) - 1.0) * 100

    daily_returns = [
        points[index]["nav"] / points[index - 1]["nav"] - 1.0
        for index in range(1, len(points))
        if points[index - 1]["nav"] > 0
    ]
    volatility = None
    if len(daily_returns) > 1:
        mean = sum(daily_returns) / len(daily_returns)
        variance = sum((value - mean) ** 2 for value in daily_returns) / (len(daily_returns) - 1)
        volatility = math.sqrt(variance) * math.sqrt(252) * 100

    peak = points[0]["nav"]
    max_drawdown = 0.0
    for item in points:
        peak = max(peak, item["nav"])
        if peak > 0:
            max_drawdown = min(max_drawdown, (item["nav"] / peak - 1.0) * 100)

    return {
        "period_years": period_years,
        "start_date": first["date"].isoformat(),
        "end_date": last["date"].isoformat(),
        "start_nav": round(first["nav"], 4),
        "latest_nav": round(last["nav"], 4),
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "annualized_volatility_pct": round(volatility, 2) if volatility is not None else None,
        "max_drawdown_pct": round(max_drawdown, 2),
        "observations": len(points),
        "anniversary_date": anniversary.isoformat(),
    }


def get_fund_analytics(fund_name: str, period_years: int = 1) -> dict[str, Any]:
    """Resolve a scheme, retrieve live NAV history, and calculate reproducible metrics."""
    if period_years not in (1, 3, 5, 10):
        raise ValueError("Supported analysis periods are 1, 3, 5, and 10 years.")

    with requests.Session() as session:
        session.headers.update(HEADERS)
        schemes = _fetch_amfi_scheme_master(session)
        scheme = _resolve_scheme(schemes, fund_name)

        source_errors: list[str] = []
        history: list[dict[str, Any]] = []
        try:
            history = _fetch_amfi_history(session, scheme["scheme_code"], period_years)
        except requests.RequestException as exc:
            source_errors.append(f"AMFI history: {type(exc).__name__}")
        if len(history) < 2:
            try:
                history = _fetch_mfapi_history(session, scheme["scheme_code"])
            except (requests.RequestException, ValueError) as exc:
                source_errors.append(f"MFapi fallback: {type(exc).__name__}")

        if len(history) < 2:
            raise MarketDataError(
                "Could not retrieve sufficient historical NAV observations. "
                + "; ".join(source_errors)
            )

    metrics = _calculate_metrics(history, period_years)
    metrics.update({
        "requested_fund": fund_name,
        "scheme_name": scheme["scheme_name"],
        "scheme_code": scheme["scheme_code"],
        "isin": scheme["isin"],
        "plan": scheme["plan"],
        "option": scheme["option"],
        "data_source": ", ".join(sorted({item.get("source", "AMFI") for item in history})),
        "source_fallback_used": any(item.get("source") != "AMFI" for item in history),
        "data_retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_method": "Historical NAV time series; metrics calculated by this application",
    })
    return metrics
