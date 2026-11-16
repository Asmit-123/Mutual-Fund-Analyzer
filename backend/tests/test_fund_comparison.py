from data_sources.fund_comparison import rank_funds


def _fund(name, cagr, volatility, drawdown):
    return {
        "scheme_name": name,
        "scheme_code": name,
        "cagr_pct": cagr,
        "total_return_pct": cagr,
        "annualized_volatility_pct": volatility,
        "max_drawdown_pct": drawdown,
    }


def test_rank_funds_prefers_balanced_risk_return_profile():
    funds = [
        _fund("High return high risk", 18.0, 30.0, -35.0),
        _fund("Balanced", 14.0, 10.0, -12.0),
        _fund("Low return low risk", 7.0, 5.0, -5.0),
    ]
    ranked = rank_funds(funds)
    assert [item["scheme_name"] for item in ranked] == [
        "Balanced", "Low return low risk", "High return high risk"
    ]
    assert [item["rank"] for item in ranked] == [1, 2, 3]


def test_rank_scores_are_bounded_and_relative():
    ranked = rank_funds([
        _fund("A", 10, 8, -8),
        _fund("B", 10, 8, -8),
    ])
    assert all(item["comparison_score"] == 50.0 for item in ranked)
    assert all(item["score_components"] == {
        "cagr_score": 50.0,
        "volatility_score": 50.0,
        "drawdown_score": 50.0,
    } for item in ranked)


def test_rank_funds_does_not_mutate_input():
    funds = [_fund("A", 10, 8, -8), _fund("B", 12, 9, -10)]
    original = [dict(item) for item in funds]
    rank_funds(funds)
    assert funds == original


def test_rank_funds_returns_empty_for_empty_input():
    assert rank_funds([]) == []
