# Cthulhu Workbench Factor Engine Guide

> **Status: Superseded（2026-07-14）**
>
> 本文仅保留作历史记录，已由 `docs/system_design/2026-07-14 FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md` 替代，不得再作为新开发或验收依据。

## Overview

The Cthulhu Workbench Factor Engine provides a web-based interface for computing, querying, and analyzing financial factors. It integrates with the Artemis Factor Engine backend to provide real-time factor calculations and rankings.

---

## 1. Factor Registry

The **Factor Registry** displays all registered factors in the system, including their metadata and data requirements.

### Table Columns

| Column | Description |
|--------|-------------|
| **Name** | Factor identifier (e.g., `roe`, `pe_ttm`) used in API calls |
| **中文名** | Chinese name of the factor |
| **Category** | Factor category: profitability, growth, quality, solvency, valuation, efficiency, per_share |
| **Formula** | Human-readable formula describing the factor calculation |
| **Unit** | Unit of the factor value (%, 倍, 天) |
| **H↑** (Higher is Better) | ✓ = higher values are better, ✗ = lower values are better |
| **Mkt Data** | Market data requirement status |

### Mkt Data Column Meaning

| Value | Meaning |
|-------|---------|
| **Yes** (Blue tag) | Factor requires market data (OHLCV bars, market cap) |
| **No** (Gray tag) | Factor only needs financial statement data |

**What "No" means**: The factor can be computed using only financial statement data (income statement, balance sheet, cash flow statement). Market data (price, volume) is not required.

**What "Yes" means**: The factor requires market data in addition to financial data. Common examples:
- Valuation factors (PE, PB, PS) require market cap (price × shares)
- Per-share factors (EPS, BPS) require share count from market data

### Example Factor Registry Entry

```
Name: pe_ttm
中文名: 市盈率TTM
Category: valuation
Formula: MC/NI_TTM
Unit: 倍
H↑: ✗
Mkt Data: Yes (Blue)
```

**Interpretation**: This is a valuation factor that calculates price-to-earnings ratio. It requires market data (for market cap) and lower values are better (cheaper stocks).

---

## 2. Compute

The **Compute** tab provides two modes for calculating factors:

### 2.1 Full Computation

Calculates factors for all active symbols in a market on a specified date.

**Parameters**:
- **Date**: The as-of date for factor calculation (YYYYMMDD format)
- **Market**: Market identifier (default: `zh_a` for A-shares)

**Usage**:
1. Enter the calculation date (e.g., `20260510`)
2. Select the market
3. Click "Run Full"

**What it does**:
- Fetches all active symbols in the specified market
- Retrieves required financial and market data for each symbol
- Computes all registered factors
- Stores results in the factor database

**Result**: Returns the count of symbols processed (e.g., "Computed 5200 symbols for 20260510")

### 2.2 Incremental Computation

Calculates factors for a specific list of symbols, useful for updating a subset of stocks.

**Parameters**:
- **Symbols**: Comma-separated symbol list (e.g., `000001,000002,600000`)
- **Date**: The as-of date for factor calculation (YYYYMMDD format)
- **Market**: Market identifier (default: `zh_a`)

**Usage**:
1. Enter symbols (comma-separated)
2. Enter the calculation date
3. Click "Run Incremental"

**Use Cases**:
- Updating newly listed stocks
- Recalculating after corporate actions
- Debugging factor calculations for specific stocks
- Testing factor changes before full recomputation

---

## 3. Snapshot

The **Snapshot** tab provides detailed factor values for a single stock on a specific date.

### Parameters

- **Symbol**: Stock code (e.g., `000001`)
- **Date**: As-of date (YYYYMMDD format)

### Output

The snapshot displays two tables:

#### 3.1 Raw Factors

Original factor values as computed by the factor engine, before normalization.

| Factor | Value |
|--------|-------|
| roe | 12.3456 |
| roa | 4.5678 |
| pe_ttm | 15.2345 |

#### 3.2 Normalized Factors

Factor values after applying normalization (z-score, min-max, etc.) for cross-factor comparison.

| Factor | Value |
|--------|-------|
| roe | 1.2345 |
| roa | 0.5678 |
| pe_ttm | -0.4321 |

**Note**: Normalized values are typically centered around 0, where:
- Positive values = above average
- Negative values = below average
- Standard deviation typically ≈ 1 for z-score normalization

### Use Cases

- Analyzing a specific stock's factor profile
- Debugging factor calculations
- Understanding factor composition before/after normalization
- Researching stock characteristics

---

## 4. Ranking

The **Ranking** tab displays the top (or bottom) N stocks for a specific factor.

### Parameters

- **Factor**: Select from all registered factors
- **Date**: As-of date (YYYYMMDD format)
- **Top N**: Number of stocks to return (1-500, default 50)

### Output

A ranked table showing:

| # | Symbol | [Factor Name] |
|---|--------|---------------|
| 1 | 000001 | 25.4321 |
| 2 | 600000 | 23.1234 |
| 3 | 000002 | 21.9876 |

### Ranking Behavior

The ranking respects the `higher_is_better` attribute of each factor:

- If `higher_is_better = ✓`: Shows top N stocks (highest values)
- If `higher_is_better = ✗`: Shows top N stocks (lowest values, which are "better")

**Example**:
- For `roe` (higher is better): Shows companies with highest ROE
- For `debt_ratio` (higher is worse): Shows companies with lowest debt ratio

### Use Cases

- Identifying best/worst performers by a factor
- Factor-based stock screening
- Backtesting factor strategies
- Researching factor distributions

---

## API Reference

All UI features are backed by the Artemis Factor Engine API:

### GET /factors/meta

Returns metadata for all registered factors.

**Response**:
```json
[
  {
    "name": "roe",
    "cn_name": "净资产收益率",
    "category": "profitability",
    "formula": "NI_TTM / avg(equity)",
    "unit": "%",
    "higher_is_better": true,
    "requires_market_data": false,
    "exclude_financial": false
  }
]
```

### POST /factors/compute/full

Trigger full factor computation for all symbols.

**Parameters**:
- `as_of_date`: YYYYMMDD
- `market`: Market identifier (default: zh_a)

**Response**:
```json
{
  "status": "completed",
  "symbols_count": 5200,
  "as_of_date": "20260510"
}
```

### POST /factors/compute/incremental

Incremental factor computation for specific symbols.

**Body**: Array of symbol strings
**Parameters**: `as_of_date`, `market`

**Response**: Same as full computation

### GET /factors/snapshot

Get factor snapshot for a single symbol.

**Parameters**:
- `symbol`: Stock code
- `as_of_date`: YYYYMMDD
- `market`: Market identifier

**Response**:
```json
{
  "raw_factors": {
    "roe": 12.3456,
    "roa": 4.5678
  },
  "norm_factors": {
    "roe": 1.2345,
    "roa": 0.5678
  },
  "meta": {
    "symbol": "000001",
    "as_of_date": "20260510"
  }
}
```

### GET /factors/rank

Get factor ranking.

**Parameters**:
- `factor_name`: Factor identifier
- `as_of_date`: YYYYMMDD
- `market`: Market identifier
- `top_n`: Number of results (default 50)

**Response**:
```json
[
  {
    "symbol": "000001",
    "roe": 25.4321
  },
  {
    "symbol": "600000",
    "roe": 23.1234
  }
]
```

---

## Best Practices

### 1. Factor Computation

- **Full computation** should be run daily after market close (typically 18:00+)
- Use **incremental computation** for testing and debugging
- Ensure financial data is up-to-date before computing factors

### 2. Data Freshness

- Factors should be computed on the latest available trading date
- Financial statement data uses `ann_date_before` to avoid look-ahead bias
- Market data should include the latest trading day's close price

### 3. Factor Interpretation

- Always check the `higher_is_better` flag before interpreting rankings
- Use normalized factors for cross-factor comparison
- Use raw factors for understanding actual values

### 4. Performance

- Full computation can take several minutes for large markets
- Use incremental computation for smaller updates
- Cache results to avoid redundant computations

---

## Troubleshooting

### Issue: "Mkt Data: No" but factor still requires price data

**Solution**: Check if the factor uses market cap (close × shares). Some factors need market data even if not explicitly marked.

### Issue: Snapshot returns empty results

**Possible causes**:
1. Symbol not in the active symbol list
2. Date is a non-trading day
3. Financial data not available for the date
4. Factor hasn't been computed for that date

**Solution**: Run full computation for the date first.

### Issue: Ranking shows unexpected order

**Check**:
1. The `higher_is_better` flag for the factor
2. Whether the date has valid factor data
3. If the factor has missing values for many stocks

### Issue: Computation is slow

**Optimizations**:
1. Use incremental computation for fewer symbols
2. Check database indexes on factor tables
3. Verify PhoenixA API response times

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-11 | Initial documentation for Cthulhu Workbench Factor Engine |
