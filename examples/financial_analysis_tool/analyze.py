"""Financial analysis command line tool powered by OpenBB."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

MISSING = "—"


@dataclass(frozen=True)
class Metric:
    """A calculated metric displayed in the final report."""

    name: str
    value: float | str | None
    unit: str = ""
    note: str = ""


@dataclass(frozen=True)
class AnalysisResult:
    """Container for the financial analysis output."""

    symbol: str
    provider: str
    price_provider: str
    period: str
    price_metrics: list[Metric]
    fundamental_metrics: list[Metric]
    observations: list[str]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a compact financial analysis report with OpenBB data."
    )
    parser.add_argument("symbol", help="Ticker symbol to analyze, for example AAPL.")
    parser.add_argument(
        "--provider",
        default="fmp",
        help="Fundamental data provider. Examples: fmp, intrinio. Default: fmp.",
    )
    parser.add_argument(
        "--price-provider",
        default="yfinance",
        help="Historical price provider. Examples: yfinance, fmp. Default: yfinance.",
    )
    parser.add_argument(
        "--period",
        choices=("annual", "quarter"),
        default="annual",
        help="Financial statement period. Default: annual.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of financial statement periods to fetch. Default: 5.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=365,
        help="Historical price lookback window in days. Default: 365.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format. Default: markdown.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to save the report instead of writing to stdout.",
    )
    parser.add_argument(
        "--export-csv-dir",
        type=Path,
        help="Optional directory for exporting raw OpenBB DataFrames as CSV files.",
    )
    return parser.parse_args()


def fetch_openbb_data(
    symbol: str,
    provider: str,
    price_provider: str,
    period: str,
    limit: int,
    lookback_days: int,
) -> dict[str, pd.DataFrame]:
    """Fetch price and financial statement data from OpenBB."""
    from openbb import obb

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    price = obb.equity.price.historical(
        symbol=symbol,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        provider=price_provider,
    ).to_dataframe()
    income = obb.equity.fundamental.income(
        symbol=symbol,
        period=period,
        limit=limit,
        provider=provider,
    ).to_dataframe()
    balance = obb.equity.fundamental.balance(
        symbol=symbol,
        period=period,
        limit=limit,
        provider=provider,
    ).to_dataframe()
    cash = obb.equity.fundamental.cash(
        symbol=symbol,
        period=period,
        limit=limit,
        provider=provider,
    ).to_dataframe()

    return {"price": price, "income": income, "balance": balance, "cash": cash}


def latest_row(frame: pd.DataFrame, date_columns: tuple[str, ...] = ("period_ending", "date")) -> pd.Series:
    """Return the latest row in a DataFrame using common date columns when available."""
    if frame.empty:
        return pd.Series(dtype="object")

    for column in date_columns:
        if column in frame.columns:
            sorted_frame = frame.assign(**{column: pd.to_datetime(frame[column], errors="coerce")}).sort_values(column)
            return sorted_frame.iloc[-1]
    return frame.iloc[-1]


def get_value(row: pd.Series, names: tuple[str, ...]) -> float | None:
    """Get the first numeric value present in a row for the provided column names."""
    for name in names:
        if name in row and pd.notna(row[name]):
            value = pd.to_numeric(row[name], errors="coerce")
            if pd.notna(value):
                return float(value)
    return None


def divide(numerator: float | None, denominator: float | None) -> float | None:
    """Divide two values and return None for missing or zero denominators."""
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def calculate_price_metrics(price: pd.DataFrame) -> list[Metric]:
    """Calculate return, volatility, and drawdown metrics from historical prices."""
    if price.empty or "close" not in price.columns:
        return [Metric("Price data", None, note="No close price data returned by the provider.")]

    sorted_price = price.copy()
    if "date" in sorted_price.columns:
        sorted_price["date"] = pd.to_datetime(sorted_price["date"], errors="coerce")
        sorted_price = sorted_price.sort_values("date")

    close = pd.to_numeric(sorted_price["close"], errors="coerce").dropna()
    if close.empty:
        return [Metric("Price data", None, note="Close prices could not be parsed as numeric values.")]

    returns = close.pct_change().dropna()
    total_return = divide(float(close.iloc[-1] - close.iloc[0]), float(close.iloc[0]))
    annualized_volatility = float(returns.std() * math.sqrt(252)) if not returns.empty else None
    max_drawdown = None
    if len(close) > 1:
        drawdowns = close / close.cummax() - 1
        max_drawdown = float(drawdowns.min())

    return [
        Metric("Latest close", float(close.iloc[-1]), "$"),
        Metric("Price return", total_return, "%", "From first to last available close in the lookback window."),
        Metric("Annualized volatility", annualized_volatility, "%", "Based on daily close-to-close returns."),
        Metric("Maximum drawdown", max_drawdown, "%", "Worst peak-to-trough move in the lookback window."),
    ]


def calculate_fundamental_metrics(income: pd.DataFrame, balance: pd.DataFrame, cash: pd.DataFrame) -> list[Metric]:
    """Calculate profitability, leverage, liquidity, and cash-flow metrics."""
    income_row = latest_row(income)
    balance_row = latest_row(balance)
    cash_row = latest_row(cash)

    revenue = get_value(income_row, ("revenue", "total_revenue"))
    gross_profit = get_value(income_row, ("gross_profit",))
    operating_income = get_value(income_row, ("operating_income", "operating_income_loss"))
    net_income = get_value(income_row, ("net_income", "net_income_common_stockholders"))
    total_assets = get_value(balance_row, ("total_assets",))
    total_equity = get_value(
        balance_row,
        ("total_shareholder_equity", "total_equity", "shareholders_equity", "stockholders_equity"),
    )
    total_debt = get_value(balance_row, ("total_debt", "short_and_long_term_debt_total"))
    current_assets = get_value(balance_row, ("total_current_assets", "current_assets"))
    current_liabilities = get_value(balance_row, ("total_current_liabilities", "current_liabilities"))
    operating_cash_flow = get_value(cash_row, ("operating_cash_flow", "net_cash_provided_by_operating_activities"))
    capital_expenditure = get_value(cash_row, ("capital_expenditure", "capital_expenditures"))
    free_cash_flow = get_value(cash_row, ("free_cash_flow",))

    if free_cash_flow is None and operating_cash_flow is not None and capital_expenditure is not None:
        free_cash_flow = operating_cash_flow + capital_expenditure

    return [
        Metric("Revenue", revenue, "$"),
        Metric("Net income", net_income, "$"),
        Metric("Gross margin", divide(gross_profit, revenue), "%"),
        Metric("Operating margin", divide(operating_income, revenue), "%"),
        Metric("Net margin", divide(net_income, revenue), "%"),
        Metric("Return on assets", divide(net_income, total_assets), "%"),
        Metric("Return on equity", divide(net_income, total_equity), "%"),
        Metric("Debt to equity", divide(total_debt, total_equity), "x"),
        Metric("Current ratio", divide(current_assets, current_liabilities), "x"),
        Metric("Free cash flow", free_cash_flow, "$"),
        Metric("Free cash flow margin", divide(free_cash_flow, revenue), "%"),
    ]


def build_observations(price_metrics: list[Metric], fundamental_metrics: list[Metric]) -> list[str]:
    """Create concise observations from calculated metrics."""
    lookup = {metric.name: metric.value for metric in price_metrics + fundamental_metrics}
    observations: list[str] = []

    net_margin = lookup.get("Net margin")
    if isinstance(net_margin, float):
        note = (
            "Net margin is positive, indicating reported profitability."
            if net_margin > 0
            else "Net margin is negative, so profitability needs review."
        )
        observations.append(note)

    fcf_margin = lookup.get("Free cash flow margin")
    if isinstance(fcf_margin, float):
        note = (
            "Free cash flow margin is positive, which supports internal funding capacity."
            if fcf_margin > 0
            else "Free cash flow margin is negative, which can pressure funding flexibility."
        )
        observations.append(note)

    debt_to_equity = lookup.get("Debt to equity")
    if isinstance(debt_to_equity, float):
        note = (
            "Debt to equity is below 1.0x, suggesting moderate balance-sheet leverage."
            if debt_to_equity < 1
            else "Debt to equity is at or above 1.0x; compare leverage with industry peers."
        )
        observations.append(note)

    max_drawdown = lookup.get("Maximum drawdown")
    if isinstance(max_drawdown, float):
        note = (
            "The lookback window includes a drawdown deeper than 20%."
            if max_drawdown < -0.2
            else "The lookback window drawdown stayed within 20%."
        )
        observations.append(note)

    if not observations:
        observations.append("Not enough complete data was returned to generate automated observations.")
    return observations


def analyze_data(
    symbol: str,
    provider: str,
    price_provider: str,
    period: str,
    frames: dict[str, pd.DataFrame],
) -> AnalysisResult:
    """Build the complete analysis result from raw OpenBB DataFrames."""
    price_metrics = calculate_price_metrics(frames.get("price", pd.DataFrame()))
    fundamental_metrics = calculate_fundamental_metrics(
        frames.get("income", pd.DataFrame()),
        frames.get("balance", pd.DataFrame()),
        frames.get("cash", pd.DataFrame()),
    )
    observations = build_observations(price_metrics, fundamental_metrics)
    return AnalysisResult(
        symbol=symbol.upper(),
        provider=provider,
        price_provider=price_provider,
        period=period,
        price_metrics=price_metrics,
        fundamental_metrics=fundamental_metrics,
        observations=observations,
    )


def format_metric_value(metric: Metric) -> str:
    """Format a metric value for Markdown output."""
    value = metric.value
    if value is None:
        return MISSING
    if isinstance(value, str):
        return value
    if metric.unit == "%":
        return f"{value * 100:.2f}%"
    if metric.unit == "x":
        return f"{value:.2f}x"
    if metric.unit == "$":
        return f"${value:,.2f}"
    return f"{value:,.2f}"


def metrics_to_markdown(metrics: list[Metric]) -> str:
    """Render metrics as a Markdown table."""
    rows = ["| Metric | Value | Notes |", "| --- | ---: | --- |"]
    for metric in metrics:
        rows.append(f"| {metric.name} | {format_metric_value(metric)} | {metric.note or MISSING} |")
    return "\n".join(rows)


def render_markdown(result: AnalysisResult) -> str:
    """Render the analysis result as Markdown."""
    observations = "\n".join(f"- {observation}" for observation in result.observations)
    return f"""# Financial Analysis: {result.symbol}

Data providers: fundamentals = `{result.provider}`, prices = `{result.price_provider}`<br>
Financial statement period: `{result.period}`

## Price Snapshot

{metrics_to_markdown(result.price_metrics)}

## Fundamentals

{metrics_to_markdown(result.fundamental_metrics)}

## Automated Observations

{observations}

> This report is for research workflow automation only and is not investment advice.
"""


def render_json(result: AnalysisResult) -> str:
    """Render the analysis result as formatted JSON."""
    return json.dumps(asdict(result), indent=2, ensure_ascii=False)


def export_csv(frames: dict[str, pd.DataFrame], directory: Path, symbol: str) -> None:
    """Export raw OpenBB DataFrames to CSV files."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(directory / f"{symbol.lower()}_{name}.csv", index=False)


def write_report(content: str, output: Path | None) -> None:
    """Write report content to a file or stdout."""
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        return
    sys.stdout.write(content)


def main() -> None:
    """Run the command line tool."""
    args = parse_args()
    frames = fetch_openbb_data(
        symbol=args.symbol,
        provider=args.provider,
        price_provider=args.price_provider,
        period=args.period,
        limit=args.limit,
        lookback_days=args.lookback_days,
    )
    result = analyze_data(
        symbol=args.symbol,
        provider=args.provider,
        price_provider=args.price_provider,
        period=args.period,
        frames=frames,
    )
    if args.export_csv_dir:
        export_csv(frames, args.export_csv_dir, args.symbol)
    renderer = render_json if args.format == "json" else render_markdown
    write_report(renderer(result), args.output)


if __name__ == "__main__":
    main()
