#!/usr/bin/env python3
"""
Factor Data Availability Checker

This script checks which factors can be computed based on available data in PhoenixA.
It queries the PhoenixA capabilities endpoint and compares factor requirements.

Usage:
    python scripts/check_factor_availability.py

Requirements:
    - PhoenixA running with /api/v2/catalog/capabilities endpoint
    - Python 3.8+
"""

import sys
import os
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import requests
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DataAvailability(str, Enum):
    """Data availability status."""
    AVAILABLE = "available"
    PARTIAL = "partial"
    MISSING = "missing"


@dataclass
class FactorDataRequirement:
    """Describes what data a factor needs."""
    factor_name: str
    factor_cn_name: str
    category: str
    requires: Set[str]  # Data sources: income, balance_sheet, cashflow, market_data
    requires_market_data: bool
    description: str


@dataclass
class DataSourceStatus:
    """Status of a data source."""
    name: str
    available: bool
    sources: Dict[str, int]  # source -> row_count
    time_range: Optional[Tuple[str, str]] = None  # (min_date, max_date)


@dataclass
class FactorAvailabilityReport:
    """Report on factor data availability."""
    factor_name: str
    factor_cn_name: str
    category: str
    status: DataAvailability
    available_sources: Set[str]
    missing_sources: Set[str]
    notes: List[str]


# Define factor requirements based on Artemis factor registry
FACTOR_REQUIREMENTS = {
    # Profitability Factors
    "roe": FactorDataRequirement(
        factor_name="roe",
        factor_cn_name="净资产收益率",
        category="profitability",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="NI_TTM / avg(equity)"
    ),
    "roa": FactorDataRequirement(
        factor_name="roa",
        factor_cn_name="总资产收益率",
        category="profitability",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="NI_TTM / avg(total_assets)"
    ),
    "gross_margin": FactorDataRequirement(
        factor_name="gross_margin",
        factor_cn_name="毛利率",
        category="profitability",
        requires={"income"},
        requires_market_data=False,
        description="(REV_TTM - COST_TTM) / REV_TTM"
    ),
    "operating_margin": FactorDataRequirement(
        factor_name="operating_margin",
        factor_cn_name="营业利润率",
        category="profitability",
        requires={"income"},
        requires_market_data=False,
        description="OPERA_PROFIT_TTM / REV_TTM"
    ),
    "net_margin": FactorDataRequirement(
        factor_name="net_margin",
        factor_cn_name="净利率",
        category="profitability",
        requires={"income"},
        requires_market_data=False,
        description="NI_TTM / REV_TTM"
    ),
    "roic": FactorDataRequirement(
        factor_name="roic",
        factor_cn_name="投入资本回报率",
        category="profitability",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="NOPAT / Invested Capital"
    ),

    # Valuation Factors
    "pe_ttm": FactorDataRequirement(
        factor_name="pe_ttm",
        factor_cn_name="市盈率TTM",
        category="valuation",
        requires={"income"},
        requires_market_data=True,
        description="MC/NI_TTM"
    ),
    "pb": FactorDataRequirement(
        factor_name="pb",
        factor_cn_name="市净率",
        category="valuation",
        requires={"balance_sheet"},
        requires_market_data=True,
        description="MC/Equity"
    ),
    "ps_ttm": FactorDataRequirement(
        factor_name="ps_ttm",
        factor_cn_name="市销率TTM",
        category="valuation",
        requires={"income"},
        requires_market_data=True,
        description="MC/REV_TTM"
    ),
    "peg": FactorDataRequirement(
        factor_name="peg",
        factor_cn_name="PEG",
        category="valuation",
        requires={"income"},
        requires_market_data=True,
        description="PE/Growth"
    ),
    "ev_to_ebitda": FactorDataRequirement(
        factor_name="ev_to_ebitda",
        factor_cn_name="EV/EBITDA",
        category="valuation",
        requires={"income", "balance_sheet"},
        requires_market_data=True,
        description="EV/EBITDA_TTM"
    ),
    "pcf": FactorDataRequirement(
        factor_name="pcf",
        factor_cn_name="市现率",
        category="valuation",
        requires={"cashflow"},
        requires_market_data=True,
        description="MC/OCF_TTM"
    ),
    "dividend_yield": FactorDataRequirement(
        factor_name="dividend_yield",
        factor_cn_name="股息率",
        category="valuation",
        requires={"balance_sheet"},  # DPS from balance_sheet
        requires_market_data=True,
        description="DPS/Close"
    ),

    # Per Share Factors
    "eps_ttm": FactorDataRequirement(
        factor_name="eps_ttm",
        factor_cn_name="每股收益TTM",
        category="per_share",
        requires={"income"},
        requires_market_data=True,
        description="NI_TTM/Shares"
    ),
    "bps": FactorDataRequirement(
        factor_name="bps",
        factor_cn_name="每股净资产",
        category="per_share",
        requires={"balance_sheet"},
        requires_market_data=True,
        description="Equity/Shares"
    ),
    "cfps": FactorDataRequirement(
        factor_name="cfps",
        factor_cn_name="每股经营现金流",
        category="per_share",
        requires={"cashflow"},
        requires_market_data=True,
        description="OCF_TTM/Shares"
    ),
    "fcf_per_share": FactorDataRequirement(
        factor_name="fcf_per_share",
        factor_cn_name="每股自由现金流",
        category="per_share",
        requires={"cashflow"},
        requires_market_data=True,
        description="FCF_TTM/Shares"
    ),
    "dps": FactorDataRequirement(
        factor_name="dps",
        factor_cn_name="每股股利",
        category="per_share",
        requires={"balance_sheet"},  # DPS from balance_sheet
        requires_market_data=False,
        description="Total Dividends/Shares"
    ),

    # Growth Factors
    "revenue_growth_yoy": FactorDataRequirement(
        factor_name="revenue_growth_yoy",
        factor_cn_name="营收同比增长",
        category="growth",
        requires={"income"},
        requires_market_data=False,
        description="REV_SQ(t)/REV_SQ(t-4Q)-1"
    ),
    "ni_growth_yoy": FactorDataRequirement(
        factor_name="ni_growth_yoy",
        factor_cn_name="净利润同比增长",
        category="growth",
        requires={"income"},
        requires_market_data=False,
        description="NI_SQ(t)/NI_SQ(t-4Q)-1"
    ),
    "revenue_cagr_3y": FactorDataRequirement(
        factor_name="revenue_cagr_3y",
        factor_cn_name="3年营收复合增长",
        category="growth",
        requires={"income"},
        requires_market_data=False,
        description="(REV_TTM(t)/REV_TTM(t-12Q))^(1/3)-1"
    ),
    "ni_cagr_3y": FactorDataRequirement(
        factor_name="ni_cagr_3y",
        factor_cn_name="3年净利润复合增长",
        category="growth",
        requires={"income"},
        requires_market_data=False,
        description="(NI_TTM(t)/NI_TTM(t-12Q))^(1/3)-1"
    ),
    "ocf_growth": FactorDataRequirement(
        factor_name="ocf_growth",
        factor_cn_name="经营现金流增长",
        category="growth",
        requires={"cashflow"},
        requires_market_data=False,
        description="OCF_TTM(t)/OCF_TTM(t-4Q)-1"
    ),

    # Quality Factors
    "accrual_ratio": FactorDataRequirement(
        factor_name="accrual_ratio",
        factor_cn_name="应计比率",
        category="quality",
        requires={"income", "cashflow", "balance_sheet"},
        requires_market_data=False,
        description="(NI_TTM - OCF_TTM) / avg(assets)"
    ),
    "cash_conversion": FactorDataRequirement(
        factor_name="cash_conversion",
        factor_cn_name="现金转换率",
        category="quality",
        requires={"income", "cashflow"},
        requires_market_data=False,
        description="OCF_TTM / NI_TTM"
    ),
    "fcf_quality": FactorDataRequirement(
        factor_name="fcf_quality",
        factor_cn_name="自由现金流覆盖率",
        category="quality",
        requires={"income", "cashflow"},
        requires_market_data=False,
        description="FCF_TTM / NI_TTM"
    ),
    "earnings_stability": FactorDataRequirement(
        factor_name="earnings_stability",
        factor_cn_name="盈利稳定性",
        category="quality",
        requires={"income"},
        requires_market_data=False,
        description="std(NI_SQ,8Q)/|mean(NI_SQ,8Q)|"
    ),
    "goodwill_ratio": FactorDataRequirement(
        factor_name="goodwill_ratio",
        factor_cn_name="商誉占比",
        category="quality",
        requires={"balance_sheet"},
        requires_market_data=False,
        description="GOODWILL/TOTAL_ASSETS"
    ),

    # Solvency Factors
    "debt_ratio": FactorDataRequirement(
        factor_name="debt_ratio",
        factor_cn_name="资产负债率",
        category="solvency",
        requires={"balance_sheet"},
        requires_market_data=False,
        description="TOTAL_LIAB/TOTAL_ASSETS"
    ),
    "current_ratio": FactorDataRequirement(
        factor_name="current_ratio",
        factor_cn_name="流动比率",
        category="solvency",
        requires={"balance_sheet"},
        requires_market_data=False,
        description="CUR_ASSETS/CUR_LIAB"
    ),
    "quick_ratio": FactorDataRequirement(
        factor_name="quick_ratio",
        factor_cn_name="速动比率",
        category="solvency",
        requires={"balance_sheet"},
        requires_market_data=False,
        description="(CUR_ASSETS-INV)/CUR_LIAB"
    ),
    "interest_coverage": FactorDataRequirement(
        factor_name="interest_coverage",
        factor_cn_name="利息保障倍数",
        category="solvency",
        requires={"income"},
        requires_market_data=False,
        description="EBIT_TTM/FIN_EXP_TTM"
    ),
    "net_debt_to_ebitda": FactorDataRequirement(
        factor_name="net_debt_to_ebitda",
        factor_cn_name="净负债/EBITDA",
        category="solvency",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="Net Debt/EBITDA_TTM"
    ),
    "cash_to_st_debt": FactorDataRequirement(
        factor_name="cash_to_st_debt",
        factor_cn_name="现金覆盖短债",
        category="solvency",
        requires={"balance_sheet"},
        requires_market_data=False,
        description="Cash / ST Debt"
    ),

    # Efficiency Factors
    "asset_turnover": FactorDataRequirement(
        factor_name="asset_turnover",
        factor_cn_name="总资产周转率",
        category="efficiency",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="REV_TTM/avg(Assets)"
    ),
    "inventory_turnover": FactorDataRequirement(
        factor_name="inventory_turnover",
        factor_cn_name="存货周转率",
        category="efficiency",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="COST_TTM/avg(INV)"
    ),
    "receivable_turnover": FactorDataRequirement(
        factor_name="receivable_turnover",
        factor_cn_name="应收账款周转率",
        category="efficiency",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="REV_TTM/avg(AR)"
    ),
    "cash_cycle": FactorDataRequirement(
        factor_name="cash_cycle",
        factor_cn_name="现金循环天数",
        category="efficiency",
        requires={"income", "balance_sheet"},
        requires_market_data=False,
        description="DSO+DIO-DPO"
    ),
    "capex_to_revenue": FactorDataRequirement(
        factor_name="capex_to_revenue",
        factor_cn_name="资本支出/营收",
        category="efficiency",
        requires={"cashflow", "income"},
        requires_market_data=False,
        description="Capex/REV_TTM"
    ),
}


def get_phoenixa_capabilities(base_url: str = "http://localhost:8080") -> Dict:
    """Query PhoenixA capabilities endpoint."""
    try:
        response = requests.get(f"{base_url}/api/v2/catalog/capabilities", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Warning: Could not connect to PhoenixA at {base_url}: {e}")
        return {}


def analyze_data_availability(capabilities: Dict) -> Dict[str, DataSourceStatus]:
    """Analyze data availability from capabilities response."""
    status = {}

    # Check bars data (market data)
    status["market_data"] = DataSourceStatus(
        name="market_data",
        available=False,
        sources={},
        time_range=None,
    )

    # Check financial_statement data
    status["income"] = DataSourceStatus(name="income", available=False, sources={}, time_range=None)
    status["balance_sheet"] = DataSourceStatus(name="balance_sheet", available=False, sources={}, time_range=None)
    status["cashflow"] = DataSourceStatus(name="cashflow", available=False, sources={}, time_range=None)

    for domain in capabilities.get("capabilities", []):
        domain_name = domain.get("domain", "")
        for table in domain.get("tables", []):
            table_name = table.get("table_name", "")
            data_sources = table.get("data_sources", [])
            time_range = table.get("time_range")

            # Check bars tables
            if table_name.startswith("bars_"):
                status["market_data"].available = True
                for ds in data_sources:
                    status["market_data"].sources[ds.get("source", "unknown")] = ds.get("row_count", 0)
                if time_range:
                    status["market_data"].time_range = (
                        time_range.get("min_date", ""),
                        time_range.get("max_date", "")
                    )

            # Check financial_statement table
            elif table_name == "financial_statement":
                capability = table.get("capability", {})
                data_types = capability.get("data_types", [])

                for data_type in data_types:
                    type_value = data_type.get("type_value", "")
                    if type_value == "income":
                        status["income"].available = True
                        for ds in data_sources:
                            if ds.get("source") == "amazing_data":
                                status["income"].sources["amazing_data"] = ds.get("row_count", 0)
                    elif type_value == "balance_sheet":
                        status["balance_sheet"].available = True
                        for ds in data_sources:
                            if ds.get("source") == "amazing_data":
                                status["balance_sheet"].sources["amazing_data"] = ds.get("row_count", 0)
                    elif type_value == "cashflow":
                        status["cashflow"].available = True
                        for ds in data_sources:
                            if ds.get("source") == "amazing_data":
                                status["cashflow"].sources["amazing_data"] = ds.get("row_count", 0)

                if time_range:
                    for ds_name in ["income", "balance_sheet", "cashflow"]:
                        if status[ds_name].available and not status[ds_name].time_range:
                            status[ds_name].time_range = (
                                time_range.get("min_date", ""),
                                time_range.get("max_date", "")
                            )

    return status


def check_factor_availability(
    factor: FactorDataRequirement,
    data_status: Dict[str, DataSourceStatus]
) -> FactorAvailabilityReport:
    """Check if a factor's data requirements are met."""
    available_sources = set()
    missing_sources = set()
    notes = []

    for source in factor.requires:
        if source == "market_data":
            if data_status.get("market_data", DataSourceStatus("", False, {})).available:
                available_sources.add(source)
            else:
                missing_sources.add(source)
                notes.append("Missing market data (OHLCV bars)")
        elif source in data_status:
            ds = data_status[source]
            if ds.available:
                available_sources.add(source)
                # Check if there's actual data
                total_rows = sum(ds.sources.values())
                if total_rows == 0:
                    missing_sources.add(source)
                    notes.append(f"{source} has no data rows")
                else:
                    notes.append(f"{source}: {total_rows:,} rows from {len(ds.sources)} source(s)")
            else:
                missing_sources.add(source)
                notes.append(f"{source} not available in financial_statement table")

    # Determine overall status
    if missing_sources:
        status = DataAvailability.MISSING
    elif available_sources == factor.requires:
        status = DataAvailability.AVAILABLE
    else:
        status = DataAvailability.PARTIAL

    return FactorAvailabilityReport(
        factor_name=factor.factor_name,
        factor_cn_name=factor.factor_cn_name,
        category=factor.category,
        status=status,
        available_sources=available_sources,
        missing_sources=missing_sources,
        notes=notes
    )


def print_report(reports: List[FactorAvailabilityReport], data_status: Dict[str, DataSourceStatus]):
    """Print a formatted report."""
    print("=" * 80)
    print("FACTOR DATA AVAILABILITY REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Print data source summary
    print("DATA SOURCE SUMMARY")
    print("-" * 80)
    for ds_name in ["income", "balance_sheet", "cashflow", "market_data"]:
        ds = data_status.get(ds_name, DataSourceStatus(ds_name, False, {}))
        status_str = "✓ AVAILABLE" if ds.available else "✗ MISSING"
        if ds.available:
            sources_str = ", ".join([f"{src} ({count:,})" for src, count in ds.sources.items()])
            time_str = ""
            if ds.time_range and ds.time_range != ("", ""):
                time_str = f" | {ds.time_range[0]} to {ds.time_range[1]}"
            print(f"{ds_name:20s} {status_str:15s} | {sources_str}{time_str}")
        else:
            print(f"{ds_name:20s} {status_str:15s}")
    print()

    # Group by category
    categories = {}
    for report in reports:
        if report.category not in categories:
            categories[report.category] = []
        categories[report.category].append(report)

    # Print factor availability by category
    for category in ["profitability", "growth", "quality", "solvency", "valuation", "efficiency", "per_share"]:
        if category not in categories:
            continue
        print(f"{category.upper()} FACTORS")
        print("-" * 80)

        available = 0
        partial = 0
        missing = 0

        for report in categories[category]:
            status_icon = {
                DataAvailability.AVAILABLE: "✓",
                DataAvailability.PARTIAL: "⚠",
                DataAvailability.MISSING: "✗",
            }[report.status]

            print(f"  {status_icon} {report.factor_name:25s} ({report.factor_cn_name})")

            if report.status == DataAvailability.AVAILABLE:
                available += 1
            elif report.status == DataAvailability.PARTIAL:
                partial += 1
                for note in report.notes:
                    print(f"    - {note}")
            else:
                missing += 1
                for missing_src in report.missing_sources:
                    print(f"    - Missing: {missing_src}")

        total = len(categories[category])
        print(f"  Summary: {available}/{total} available, {partial} partial, {missing} missing")
        print()

    # Overall summary
    total_factors = len(reports)
    total_available = sum(1 for r in reports if r.status == DataAvailability.AVAILABLE)
    total_partial = sum(1 for r in reports if r.status == DataAvailability.PARTIAL)
    total_missing = sum(1 for r in reports if r.status == DataAvailability.MISSING)

    print("=" * 80)
    print("OVERALL SUMMARY")
    print("-" * 80)
    print(f"Total Factors:     {total_factors}")
    print(f"Fully Available:   {total_available} ({100*total_available//total_factors if total_factors else 0}%)")
    print(f"Partially Available: {total_partial} ({100*total_partial//total_factors if total_factors else 0}%)")
    print(f"Missing Data:      {total_missing} ({100*total_missing//total_factors if total_factors else 0}%)")
    print("=" * 80)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Check factor data availability")
    parser.add_argument(
        "--phoenixa-url",
        default="http://localhost:8080",
        help="PhoenixA base URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Get capabilities from PhoenixA
    capabilities = get_phoenixa_capabilities(args.phoenixa_url)

    # Analyze data availability
    data_status = analyze_data_availability(capabilities)

    # Check each factor
    reports = []
    for factor_req in FACTOR_REQUIREMENTS.values():
        report = check_factor_availability(factor_req, data_status)
        reports.append(report)

    if args.output == "json":
        # Output as JSON
        result = {
            "generated_at": datetime.now().isoformat(),
            "data_sources": {
                name: {
                    "available": ds.available,
                    "sources": ds.sources,
                    "time_range": ds.time_range,
                }
                for name, ds in data_status.items()
            },
            "factors": [
                {
                    "name": r.factor_name,
                    "cn_name": r.factor_cn_name,
                    "category": r.category,
                    "status": r.status.value,
                    "available_sources": list(r.available_sources),
                    "missing_sources": list(r.missing_sources),
                    "notes": r.notes,
                }
                for r in reports
            ],
            "summary": {
                "total": len(reports),
                "available": sum(1 for r in reports if r.status == DataAvailability.AVAILABLE),
                "partial": sum(1 for r in reports if r.status == DataAvailability.PARTIAL),
                "missing": sum(1 for r in reports if r.status == DataAvailability.MISSING),
            }
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Print text report
        print_report(reports, data_status)


if __name__ == "__main__":
    main()
