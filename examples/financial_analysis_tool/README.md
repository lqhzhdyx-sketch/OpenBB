# Financial Analysis Tool

This example is a small command line tool that uses the OpenBB Platform to create a compact financial analysis report for a public company ticker.

It fetches:

- historical equity prices through `obb.equity.price.historical`
- income statements through `obb.equity.fundamental.income`
- balance sheets through `obb.equity.fundamental.balance`
- cash-flow statements through `obb.equity.fundamental.cash`

The tool then calculates a concise set of price, profitability, leverage, liquidity, and cash-flow metrics and renders the results as Markdown or JSON.

## Install

From an environment with OpenBB installed:

```bash
pip install openbb openbb-yfinance openbb-fmp
```

Some fundamental providers require API keys. Configure credentials with OpenBB user settings or choose a provider available in your environment.

## Usage

Run a Markdown report for Apple:

```bash
python examples/financial_analysis_tool/analyze.py AAPL --provider fmp --price-provider yfinance
```

Save the report and export raw data:

```bash
python examples/financial_analysis_tool/analyze.py MSFT \
  --provider fmp \
  --price-provider yfinance \
  --output reports/msft.md \
  --export-csv-dir reports/raw
```

Return machine-readable JSON:

```bash
python examples/financial_analysis_tool/analyze.py NVDA --format json
```

## Metrics included

Price metrics:

- latest close
- lookback-window price return
- annualized volatility
- maximum drawdown

Fundamental metrics:

- revenue and net income
- gross, operating, and net margin
- return on assets and return on equity
- debt to equity and current ratio
- free cash flow and free cash flow margin

> This example is for research workflow automation only and is not investment advice.
