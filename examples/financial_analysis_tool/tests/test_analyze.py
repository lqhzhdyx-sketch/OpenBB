"""Tests for the financial analysis example tool."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

MODULE_PATH = Path(__file__).resolve().parents[1] / "analyze.py"
SPEC = importlib.util.spec_from_file_location("financial_analysis_tool_analyze", MODULE_PATH)
analyze = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = analyze
SPEC.loader.exec_module(analyze)


def test_calculate_price_metrics() -> None:
    """Calculate price metrics from deterministic close prices."""
    prices = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4),
            "close": [100.0, 110.0, 105.0, 120.0],
        }
    )

    metrics = {metric.name: metric.value for metric in analyze.calculate_price_metrics(prices)}

    assert metrics["Latest close"] == 120.0
    assert round(metrics["Price return"], 4) == 0.2
    assert round(metrics["Maximum drawdown"], 4) == -0.0455


def test_calculate_fundamental_metrics() -> None:
    """Calculate common financial ratios from sample statements."""
    income = pd.DataFrame(
        {
            "period_ending": ["2023-12-31", "2024-12-31"],
            "revenue": [900.0, 1000.0],
            "gross_profit": [360.0, 420.0],
            "operating_income": [180.0, 220.0],
            "net_income": [90.0, 120.0],
        }
    )
    balance = pd.DataFrame(
        {
            "period_ending": ["2024-12-31"],
            "total_assets": [2000.0],
            "total_shareholder_equity": [800.0],
            "total_debt": [400.0],
            "total_current_assets": [500.0],
            "total_current_liabilities": [250.0],
        }
    )
    cash = pd.DataFrame(
        {
            "period_ending": ["2024-12-31"],
            "operating_cash_flow": [200.0],
            "capital_expenditure": [-50.0],
        }
    )

    metrics = {metric.name: metric.value for metric in analyze.calculate_fundamental_metrics(income, balance, cash)}

    assert metrics["Gross margin"] == 0.42
    assert metrics["Net margin"] == 0.12
    assert metrics["Return on equity"] == 0.15
    assert metrics["Debt to equity"] == 0.5
    assert metrics["Current ratio"] == 2.0
    assert metrics["Free cash flow"] == 150.0
    assert metrics["Free cash flow margin"] == 0.15


def test_render_markdown_contains_sections() -> None:
    """Render the final Markdown report with expected sections."""
    result = analyze.AnalysisResult(
        symbol="AAPL",
        provider="fmp",
        price_provider="yfinance",
        period="annual",
        price_metrics=[analyze.Metric("Latest close", 123.45, "$")],
        fundamental_metrics=[analyze.Metric("Net margin", 0.25, "%")],
        observations=["Example observation."],
    )

    report = analyze.render_markdown(result)

    assert "# Financial Analysis: AAPL" in report
    assert "## Price Snapshot" in report
    assert "## Fundamentals" in report
    assert "Example observation." in report
