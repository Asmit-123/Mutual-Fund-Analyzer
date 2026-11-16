from datetime import date
import math

import pytest

from data_sources.mutual_fund_nav import (
    MarketDataError,
    _calculate_metrics,
    _validated_observations,
)


def nav(day: str, value: float):
    return {"date": date.fromisoformat(day), "nav": value, "source": "test"}


def test_one_year_window_uses_nav_on_or_before_anniversary():
    observations = [
        nav("2025-11-12", 93.5),
        nav("2025-11-13", 94.0058),
        nav("2025-11-17", 94.5101),
        nav("2026-11-13", 94.2594),
    ]
    result = _calculate_metrics(observations, 1)
    assert result["anniversary_date"] == "2025-11-13"
    assert result["start_date"] == "2025-11-13"
    assert result["end_date"] == "2026-11-13"
    assert result["start_nav"] == 94.0058
    assert result["latest_nav"] == 94.2594
    assert result["total_return_pct"] == 0.27


def test_weekend_or_holiday_anniversary_uses_previous_available_nav():
    observations = [
        nav("2024-06-14", 100.0),
        nav("2024-06-17", 101.0),
        nav("2025-06-15", 105.0),
    ]
    result = _calculate_metrics(observations, 1)
    assert result["anniversary_date"] == "2024-06-15"
    assert result["start_date"] == "2024-06-14"


def test_metrics_are_anchored_to_latest_observation_not_server_date():
    result = _calculate_metrics([
        nav("2025-11-13", 94.0058),
        nav("2026-11-13", 94.2594),
    ], 1)
    assert result["start_date"] == "2025-11-13"
    assert result["end_date"] == "2026-11-13"


def test_duplicate_identical_dates_are_removed_and_counted():
    observations = [
        nav("2025-11-13", 94.0058),
        nav("2025-11-13", 94.0058),
        nav("2026-11-13", 94.2594),
        nav("2026-11-13", 94.2594),
    ]
    result = _calculate_metrics(observations, 1)
    assert result["observations"] == 2
    assert result["periodic_returns"] == 1
    assert result["data_quality"]["duplicate_observations_removed"] == 2


def test_conflicting_values_for_same_date_are_rejected():
    with pytest.raises(MarketDataError, match="Conflicting NAV values"):
        _calculate_metrics([
            nav("2025-11-13", 94.0058),
            nav("2025-11-13", 94.1058),
            nav("2026-11-13", 94.2594),
        ], 1)


def test_invalid_and_non_finite_nav_rows_are_discarded():
    observations = [
        nav("2025-11-13", 100.0),
        nav("2025-11-14", float("nan")),
        nav("2025-11-15", float("inf")),
        nav("2025-11-16", -1.0),
        nav("2026-11-13", 101.0),
    ]
    result = _calculate_metrics(observations, 1)
    assert result["observations"] == 2
    assert result["data_quality"]["invalid_rows_discarded"] == 3


def test_periodic_return_count_is_observations_minus_one():
    result = _calculate_metrics([
        nav("2025-11-13", 100.0),
        nav("2025-11-14", 101.0),
        nav("2025-11-17", 99.0),
        nav("2025-11-18", 102.0),
        nav("2026-11-13", 105.0),
    ], 1)
    assert result["observations"] == 5
    assert result["periodic_returns"] == 4


def test_volatility_uses_sample_standard_deviation_and_sqrt_252():
    values = [100.0, 101.0, 99.0, 102.0, 105.0]
    observations = [
        nav(day, value)
        for day, value in zip(
            ["2025-11-13", "2025-11-14", "2025-11-17", "2025-11-18", "2026-11-13"],
            values,
        )
    ]
    result = _calculate_metrics(observations, 1)
    returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values))]
    mean = sum(returns) / len(returns)
    sample_std = math.sqrt(sum((x - mean) ** 2 for x in returns) / (len(returns) - 1))
    expected = sample_std * math.sqrt(252) * 100
    assert result["annualized_volatility_pct"] == round(expected, 2)


def test_maximum_drawdown_is_peak_to_subsequent_trough():
    result = _calculate_metrics([
        nav("2025-11-13", 100.0),
        nav("2025-12-13", 120.0),
        nav("2026-01-13", 108.0),
        nav("2026-02-13", 126.0),
        nav("2026-11-13", 113.4),
    ], 1)
    assert result["max_drawdown_pct"] == -10.0


def test_calendar_gaps_are_reported_not_assumed_to_be_missing_trading_days():
    result = _calculate_metrics([
        nav("2025-11-13", 100.0),
        nav("2025-11-14", 101.0),
        nav("2025-11-24", 102.0),
        nav("2026-11-13", 103.0),
    ], 1)
    assert result["data_quality"]["largest_calendar_gap_days"] == 354
    assert result["data_quality"]["calendar_gaps_over_7_days"] == 2


def test_leap_day_anniversary_uses_february_28():
    result = _calculate_metrics([
        nav("2023-02-28", 100.0),
        nav("2024-02-29", 105.0),
    ], 1)
    assert result["anniversary_date"] == "2023-02-28"
    assert result["start_date"] == "2023-02-28"


def test_insufficient_history_is_rejected():
    with pytest.raises(MarketDataError, match="Insufficient"):
        _calculate_metrics([nav("2025-11-13", 100.0)], 1)
