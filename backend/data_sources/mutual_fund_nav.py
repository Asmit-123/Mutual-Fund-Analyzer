"""Provider-agnostic Indian mutual-fund NAV ingestion and analytics.

Primary source: AMFI public NAV feeds and historical NAV archive.
Fallback: MFapi.in JSON mirror when AMFI history is unavailable.

All analytics run on a validated, date-deduplicated NAV series. Calendar gaps
are reported as data-quality signals rather than treated as missing trading
days, because weekends and exchange holidays are not NAV publication days.
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
ANNUALIZATION_DAYS = 252
LONG_CALENDAR_GAP_DAYS = 7


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
        if len(fields) >= 8 and fields[0].isdigit():
            code, isin1, isin2, name, plan, option, nav, nav_date = fields[:8]
        elif len(fields) >= 6 and fields[0].isdigit():
            code, isin1, isin2, name, nav, nav_date = fields[:6]
            plan, option = "", ""
        else:
            continue
        try:
            nav_value = float(nav)
        except (TypeError, ValueError):
            continue
        if not name or not math.isfinite(nav_value) or nav_value <= 0:
            continue
        schemes.append({
            "scheme_code": code, "isin": isin1 or isin2, "scheme_name": name,
            "plan": plan, "option": option, "latest_nav": nav,
            "latest_date": nav_date,
        })
    return schemes


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _scheme_display_name(item: dict[str, str]) -> str:
    """Build a searchable/displayable name across AMFI's split metadata columns."""
    parts = [
        item.get("scheme_name", ""),
        item.get("plan", ""),
        item.get("option", ""),
    ]
    return " - ".join(part.strip() for part in parts if part and part.strip())


def _resolve_scheme(schemes: list[dict[str, str]], requested_name: str) -> dict[str, str]:
    """Resolve the closest unambiguous scheme, preferring Direct Growth."""
    needle = _normalize_name(requested_name)
    if not needle:
        raise MarketDataError("A fund name is required.")

    exact = [
        item for item in schemes
        if _normalize_name(_scheme_display_name(item)) == needle
        or _normalize_name(item["scheme_name"]) == needle
    ]
    if exact:
        matches = exact
    else:
        tokens = set(needle.split())
        matches = [
            item for item in schemes
            if tokens and tokens.issubset(
                set(_normalize_name(_scheme_display_name(item)).split())
            )
        ]
    if not matches:
        raise MarketDataError(
            f"No matching scheme found in AMFI's current scheme feed for '{requested_name}'."
        )

    # If the request explicitly asks for Direct or Growth, do not silently
    # return a Regular or IDCW variant.
    requested_tokens = set(needle.split())
    if "direct" in requested_tokens:
        matches = [item for item in matches if "direct" in (
            item.get("plan", "") + " " + item.get("scheme_name", "")
        ).lower()]
    if "growth" in requested_tokens:
        matches = [item for item in matches if "growth" in (
            item.get("option", "") + " " + item.get("scheme_name", "")
        ).lower()]
    if not matches:
        raise MarketDataError(
            f"AMFI did not return the requested plan/option for '{requested_name}'."
        )

    def score(item: dict[str, str]) -> tuple[int, int, int]:
        full_name = _normalize_name(_scheme_display_name(item))
        return (
            int("direct" in (item.get("plan", "") + " " + full_name).lower()),
            int("growth" in (item.get("option", "") + " " + full_name).lower()),
            int(full_name == needle),
        )

    ranked = sorted(matches, key=score, reverse=True)
    if len(ranked) > 1 and score(ranked[0]) == score(ranked[1]):
        raise MarketDataError(
            "The fund name matches multiple AMFI schemes. Specify the exact plan and option."
        )
    return ranked[0]


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
        nav_candidates = fields[4:-1]
        nav_text = next((v for v in nav_candidates if re.fullmatch(r"\d+(?:\.\d+)?", v)), None)
        nav_date = _parse_date(fields[-1])
        try:
            nav = float(nav_text) if nav_text is not None else float("nan")
        except ValueError:
            continue
        if nav_date and math.isfinite(nav) and nav > 0:
            observations.append({"date": nav_date, "nav": nav, "source": "AMFI"})
    return observations


def _fetch_amfi_history(
    session: requests.Session, scheme_code: str, period_years: int
) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=round(period_years * 365.25) + 10)
    observations: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=89), end)
        observations.extend(_amfi_history_chunk(session, scheme_code, cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return observations


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
    observations = []
    for row in payload.get("data", []):
        nav_date = _parse_date(str(row.get("date", "")))
        try:
            nav = float(row.get("nav"))
        except (TypeError, ValueError):
            continue
        if nav_date and math.isfinite(nav) and nav > 0:
            observations.append({"date": nav_date, "nav": nav, "source": "MFapi.in"})
    return observations


def _anniversary_date(as_of: date, years: int) -> date:
    """Subtract calendar years, handling leap-day anniversaries safely."""
    try:
        return as_of.replace(year=as_of.year - years)
    except ValueError:
        return as_of.replace(year=as_of.year - years, day=28)


def _validated_observations(
    observations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Normalize rows, discard invalid NAVs, and deduplicate calendar dates.

    Identical duplicate rows are harmless. Conflicting NAV values for the
    same date are rejected instead of selecting an arbitrary provider row.
    """
    by_date: dict[date, dict[str, Any]] = {}
    invalid_rows = 0
    duplicates_removed = 0
    for item in observations:
        raw_date = item.get("date")
        if isinstance(raw_date, datetime):
            nav_date = raw_date.date()
        elif isinstance(raw_date, date):
            nav_date = raw_date
        elif isinstance(raw_date, str):
            nav_date = _parse_date(raw_date)
        else:
            nav_date = None
        try:
            nav = float(item.get("nav"))
        except (TypeError, ValueError):
            nav = float("nan")
        if nav_date is None or not math.isfinite(nav) or nav <= 0:
            invalid_rows += 1
            continue
        normalized = {**item, "date": nav_date, "nav": nav}
        existing = by_date.get(nav_date)
        if existing is not None:
            if not math.isclose(existing["nav"], nav, rel_tol=0, abs_tol=1e-8):
                raise MarketDataError(
                    f"Conflicting NAV values were received for {nav_date.isoformat()}."
                )
            duplicates_removed += 1
            continue
        by_date[nav_date] = normalized
    ordered = [by_date[day] for day in sorted(by_date)]
    return ordered, invalid_rows, duplicates_removed


def _calculate_metrics(
    observations: list[dict[str, Any]], period_years: int
) -> dict[str, Any]:
    if period_years not in (1, 3, 5, 10):
        raise ValueError("Supported analysis periods are 1, 3, 5, and 10 years.")

    ordered, invalid_rows, duplicates_removed = _validated_observations(observations)
    if len(ordered) < 2:
        raise MarketDataError("Insufficient valid, distinct NAV observations.")

    last = ordered[-1]
    anniversary = _anniversary_date(last["date"], period_years)
    eligible_starts = [i for i, item in enumerate(ordered) if item["date"] <= anniversary]
    if not eligible_starts:
        raise MarketDataError(
            f"NAV history does not reach the {period_years}-year anniversary "
            f"({anniversary.isoformat()})."
        )
    points = ordered[eligible_starts[-1]:]
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

    periodic_returns = [
        points[i]["nav"] / points[i - 1]["nav"] - 1.0
        for i in range(1, len(points))
    ]
    volatility = None
    if len(periodic_returns) > 1:
        mean_return = sum(periodic_returns) / len(periodic_returns)
        sample_variance = sum(
            (value - mean_return) ** 2 for value in periodic_returns
        ) / (len(periodic_returns) - 1)
        volatility = math.sqrt(sample_variance) * math.sqrt(ANNUALIZATION_DAYS) * 100

    running_peak = points[0]["nav"]
    max_drawdown = 0.0
    for item in points:
        running_peak = max(running_peak, item["nav"])
        max_drawdown = min(max_drawdown, (item["nav"] / running_peak - 1.0) * 100)

    gaps = [
        (points[i]["date"] - points[i - 1]["date"]).days
        for i in range(1, len(points))
    ]
    largest_gap = max(gaps, default=0)
    long_gaps = sum(gap > LONG_CALENDAR_GAP_DAYS for gap in gaps)

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
        "periodic_returns": len(periodic_returns),
        "anniversary_date": anniversary.isoformat(),
        "data_quality": {
            "invalid_rows_discarded": invalid_rows,
            "duplicate_observations_removed": duplicates_removed,
            "distinct_nav_dates": len(points),
            "periodic_return_count": len(periodic_returns),
            "annualization_factor": ANNUALIZATION_DAYS,
            "volatility_method": "sample standard deviation of consecutive NAV returns, annualized by sqrt(252)",
            "drawdown_method": "maximum peak-to-subsequent-trough decline on the NAV series",
            "largest_calendar_gap_days": largest_gap,
            "calendar_gaps_over_7_days": long_gaps,
            "calendar_gaps_are_not_assumed_to_be_missing_trading_days": True,
        },
    }


def get_fund_analytics(fund_name: str, period_years: int = 1) -> dict[str, Any]:
    """Resolve a scheme, retrieve live NAV history, validate and calculate metrics."""
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
    valid_rows, invalid_rows, duplicates_removed = _validated_observations(history)
    metrics["data_quality"].update({
        "invalid_rows_discarded": invalid_rows,
        "duplicate_observations_removed": duplicates_removed,
        "source_observation_rows": len(history),
    })
    latest_feed_date = _parse_date(scheme.get("latest_date", ""))
    latest_feed_nav = float(scheme["latest_nav"])
    history_latest = valid_rows[-1]
    metrics.update({
        "requested_fund": fund_name,
        "scheme_name": scheme["scheme_name"],
        "scheme_code": scheme["scheme_code"],
        "isin": scheme["isin"],
        "plan": scheme["plan"],
        "option": scheme["option"],
        "data_source": ", ".join(sorted({item.get("source", "AMFI") for item in history})),
        "source_fallback_used": any(item.get("source") != "AMFI" for item in history),
        "latest_scheme_feed_date": latest_feed_date.isoformat() if latest_feed_date else None,
        "latest_scheme_feed_nav": round(latest_feed_nav, 4),
        "history_latest_matches_scheme_feed": bool(
            latest_feed_date == history_latest["date"]
            and math.isclose(latest_feed_nav, history_latest["nav"], rel_tol=0, abs_tol=0.00005)
        ),
        "data_retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_method": "Historical NAV time series; metrics calculated and validated by this application",
    })
    return metrics
