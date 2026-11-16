from datetime import date

from data_sources.mutual_fund_nav import _calculate_metrics


def nav(day: str, value: float):
    return {"date": date.fromisoformat(day), "nav": value, "source": "test"}


def test_one_year_window_uses_nav_on_or_before_anniversary():
    observations = [
        nav("2025-11-12", 93.5),
        nav("2025-11-13", 94.0058),
        # The next NAV after the anniversary must not be selected as start.
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
        # Anniversary is Saturday 2024-06-15.
        nav("2024-06-17", 101.0),
        nav("2025-06-15", 105.0),
    ]

    result = _calculate_metrics(observations, 1)

    assert result["anniversary_date"] == "2024-06-15"
    assert result["start_date"] == "2024-06-14"


def test_metrics_are_anchored_to_latest_observation_not_server_date():
    observations = [
        nav("2025-11-13", 94.0058),
        nav("2026-11-13", 94.2594),
    ]

    result = _calculate_metrics(observations, 1)

    assert result["start_date"] == "2025-11-13"
    assert result["end_date"] == "2026-11-13"
