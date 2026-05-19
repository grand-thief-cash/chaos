from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.bi_engine.contracts.metric_definitions import METRIC_DEFINITION_MAP, METRIC_DEFINITIONS
from artemis.engines.factor_engine.ttm import normalize_date, normalize_period
from artemis.log.logger import get_logger
from artemis.models.bi import (
    BICompanyMeta,
    BIDashboardResponse,
    BIDriverSummaryItem,
    BIDupontComparisonRow,
    BIDupontNode,
    BIDupontResponse,
    BIIndustryMeta,
    BIInsightHighlight,
    BIInsightResponse,
    BIMetricDefinition,
    BIMetricValue,
    BIMetricsMetaResponse,
    BIPeerComparisonRequest,
    BIPeerComparisonResponse,
    BIPeerComparisonRow,
    BIQualityPanel,
    BIQualityResponse,
    BIQualityTableRow,
    BISecuritySearchItem,
    BISecuritySearchResponse,
    BISourceNote,
    BISummaryCard,
    BITrendSection,
    BITrendSeries,
    BIWarning,
)

logger = get_logger("bi_service")

COMMON_TOP_LEVEL_FIELDS = [
    "symbol",
    "market",
    "security_name",
    "reporting_period",
    "ann_date",
    "comp_type_code",
]

INCOME_FIELDS = [
    "TOT_OPERA_REV",
    "OPERA_PROFIT",
    "TOTAL_PROFIT",
    "NET_PRO_EXCL_MIN_INT_INC",
    "TOT_OPERA_COST",
    "LESS_OPERA_COST",
    "LESS_SELLING_EXP",
    "LESS_ADMIN_EXP",
    "LESS_FIN_EXP",
    "RD_EXP",
    "EBIT",
    "EBITDA",
]

BALANCE_FIELDS = [
    "TOTAL_ASSETS",
    "TOTAL_LIAB",
    "TOTAL_CUR_ASSETS",
    "TOTAL_CUR_LIAB",
    "TOT_SHARE_EQUITY_EXCL_MIN_INT",
    "INV",
    "ACCT_RECEIVABLE",
    "CURRENCY_CAP",
    "ST_BORROWING",
    "LT_LOAN",
    "BONDS_PAYABLE",
]

CASHFLOW_FIELDS = [
    "NET_CASH_FLOW_OPERA_ACT",
    "NET_CASH_FLOW_INV_ACT",
    "NET_CASH_FLOW_FIN_ACT",
    "FREE_CASH_FLOW",
    "CASH_PAID_PUR_CONST_FIOLTA",
    "CASH_RECP_SG_AND_RS",
    "NET_INCR_CASH_AND_CASH_EQU",
]

AMOUNT_METRIC_CODES = {
    "revenue_total",
    "operating_profit",
    "net_profit_parent",
    "operating_cashflow",
    "total_assets",
    "total_liab",
    "equity_parent",
    "free_cash_flow",
    "currency_cap",
    "short_borrowing",
    "long_term_loan",
    "bonds_payable",
}

PHASE1_METRIC_CODES = {
    "revenue_total",
    "operating_profit",
    "net_profit_parent",
    "operating_cashflow",
    "total_assets",
    "debt_ratio",
    "roe",
    "roa",
    "net_margin",
    "operating_profit_margin",
    "period_expense_ratio",
    "rd_expense_ratio",
    "ocf_to_profit",
    "ocf_to_revenue",
    "free_cash_flow",
    "asset_turnover",
    "ar_turnover",
    "inventory_turnover",
    "current_ratio",
    "quick_ratio",
    "currency_cap",
    "short_borrowing",
    "long_term_loan",
    "bonds_payable",
    "equity_multiplier",
}

DEFAULT_PEER_METRIC_CODES = [
    "revenue_total",
    "net_profit_parent",
    "roe",
    "debt_ratio",
    "operating_cashflow",
]

DEFAULT_INSIGHT_METRIC_CODES = [
    "revenue_total",
    "operating_profit",
    "net_profit_parent",
    "operating_cashflow",
    "debt_ratio",
    "asset_turnover",
    "ocf_to_profit",
]


@dataclass
class FinancialBundle:
    security: Dict[str, Any]
    taxonomy: List[Dict[str, Any]]
    income: List[Dict[str, Any]]
    balance_sheet: List[Dict[str, Any]]
    cashflow: List[Dict[str, Any]]
    latest_period: str


class BIService:
    def get_metric_definitions(self) -> BIMetricsMetaResponse:
        metrics = [
            BIMetricDefinition(**item)
            for item in METRIC_DEFINITIONS
            if item.get("code") in PHASE1_METRIC_CODES
        ]
        return BIMetricsMetaResponse(version="v1", metrics=metrics)

    def search_securities(self, *, query: str, market: str = "zh_a", limit: int = 20) -> BISecuritySearchResponse:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return BISecuritySearchResponse(query="", market=market, total=0, items=[])

        client = self._build_phoenix_client()
        securities = client.get_securities(asset_type="stock", market=market, limit=20000)
        lowered = normalized_query.lower()

        def _score(item: Dict[str, Any]) -> tuple[int, str]:
            symbol = str(item.get("symbol") or "")
            name = str(item.get("name") or "")
            if symbol == normalized_query:
                return (0, symbol)
            if symbol.startswith(normalized_query):
                return (1, symbol)
            if lowered in name.lower():
                return (2, symbol)
            return (3, symbol)

        filtered = [
            value for value in securities.values()
            if normalized_query in str(value.get("symbol") or "") or lowered in str(value.get("name") or "").lower()
        ]
        filtered.sort(key=_score)
        items = [
            BISecuritySearchItem(
                symbol=str(item.get("symbol") or ""),
                name=str(item.get("name") or ""),
                exchange=str(item.get("exchange") or ""),
                market=str(item.get("market") or market),
                asset_type=str(item.get("asset_type") or "stock"),
                status=str(item.get("status") or ""),
            )
            for item in filtered[: max(1, limit)]
        ]
        return BISecuritySearchResponse(query=normalized_query, market=market, total=len(items), items=items)

    def get_peer_comparison(self, req: BIPeerComparisonRequest) -> BIPeerComparisonResponse:
        symbols = self._resolve_peer_symbols(req)
        if not symbols:
            raise ValueError("No peer symbols available for comparison")

        metric_codes = [code for code in (req.metrics or DEFAULT_PEER_METRIC_CODES) if code in METRIC_DEFINITION_MAP]
        if not metric_codes:
            raise ValueError("No valid metrics requested for comparison")

        rows: List[BIPeerComparisonRow] = []
        for symbol in symbols:
            try:
                bundle = self._load_bundle(symbol=symbol, as_of_date=req.as_of_date, market=req.market, source=req.source)
                if not bundle.latest_period:
                    continue
                company = self._build_company_meta(bundle, symbol=symbol, market=req.market)
                latest_metrics = self._compute_snapshot_metrics(bundle, bundle.latest_period)
                last_year_metrics = self._compute_snapshot_metrics(bundle, self._same_period_last_year(bundle.latest_period))
                rows.append(
                    BIPeerComparisonRow(
                        symbol=symbol,
                        company_name=company.name,
                        industry_name=company.industry.name,
                        metrics={
                            code: self._make_metric_value(code, latest_metrics, last_year_metrics, bundle.latest_period)
                            for code in metric_codes
                        },
                    )
                )
            except Exception as exc:
                logger.warning({"event": "bi_peer_comparison_symbol_skipped", "symbol": symbol, "error": str(exc)})

        return BIPeerComparisonResponse(
            as_of_date=self._to_api_date(req.as_of_date),
            market=req.market,
            industry_code=req.industry_code,
            requested_metrics=metric_codes,
            rows=rows,
        )

    def get_company_insight(
        self,
        *,
        symbol: str,
        as_of_date: str,
        market: str = "zh_a",
        source: str = "amazing_data",
    ) -> BIInsightResponse:
        bundle = self._load_bundle(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
        company = self._build_company_meta(bundle, symbol=symbol, market=market)
        latest_period = bundle.latest_period
        if not latest_period:
            raise ValueError(f"No financial data available for symbol={symbol}")

        latest_metrics = self._compute_snapshot_metrics(bundle, latest_period)
        last_year_metrics = self._compute_snapshot_metrics(bundle, self._same_period_last_year(latest_period))
        warnings = self._build_dashboard_warnings(latest_metrics, last_year_metrics)

        structured_highlights = self._build_structured_highlights(latest_metrics, last_year_metrics)
        trend_summary = self._build_insight_trend_summary(latest_metrics, last_year_metrics)
        headline = structured_highlights[0].message if structured_highlights else "当前暂无足够结构化摘要"

        return BIInsightResponse(
            symbol=symbol,
            as_of_date=self._to_api_date(as_of_date),
            latest_period=latest_period,
            company=company,
            headline=headline,
            structured_highlights=structured_highlights,
            anomalies=warnings,
            trend_summary=trend_summary,
            source_notes=[
                BISourceNote(
                    section="insight",
                    statement_types=["income", "balance_sheet", "cashflow"],
                    pit_rule="ann_date_before",
                    metric_version="v1",
                )
            ],
        )

    def get_company_dashboard(
        self,
        *,
        symbol: str,
        as_of_date: str,
        market: str = "zh_a",
        source: str = "amazing_data",
    ) -> BIDashboardResponse:
        bundle = self._load_bundle(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
        company = self._build_company_meta(bundle, symbol=symbol, market=market)
        latest_period = bundle.latest_period
        if not latest_period:
            raise ValueError(f"No financial data available for symbol={symbol}")

        latest_metrics = self._compute_snapshot_metrics(bundle, latest_period)
        same_period_metrics = self._compute_snapshot_metrics(bundle, self._same_period_last_year(latest_period))

        kpi_codes = [
            "revenue_total",
            "operating_profit",
            "net_profit_parent",
            "operating_cashflow",
            "total_assets",
            "debt_ratio",
            "roe",
            "roa",
        ]
        kpis = [self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period) for code in kpi_codes]

        summary_cards = [
            BISummaryCard(
                code="profit_summary",
                title="盈利摘要",
                items=[
                    self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
                    for code in ["revenue_total", "operating_profit", "net_profit_parent"]
                ],
            ),
            BISummaryCard(
                code="cash_summary",
                title="现金摘要",
                items=[
                    self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
                    for code in ["operating_cashflow", "ocf_to_profit"]
                ],
            ),
            BISummaryCard(
                code="balance_summary",
                title="资产负债摘要",
                items=[
                    self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
                    for code in ["debt_ratio", "current_ratio", "total_assets"]
                ],
            ),
        ]

        trend_sections = [
            self._build_trend_section(
                code="revenue_profit_trend",
                title="收入 / 利润趋势",
                periods=self._recent_periods(bundle.income, limit=6),
                bundle=bundle,
                metric_codes=["revenue_total", "operating_profit", "net_profit_parent"],
            ),
            self._build_trend_section(
                code="cashflow_vs_profit_trend",
                title="经营现金流 vs 归母净利润",
                periods=self._recent_common_periods(bundle.income, bundle.cashflow, limit=6),
                bundle=bundle,
                metric_codes=["operating_cashflow", "net_profit_parent"],
            ),
            self._build_trend_section(
                code="balance_structure_trend",
                title="总资产 / 总负债 / 归母权益结构",
                periods=self._recent_periods(bundle.balance_sheet, limit=6),
                bundle=bundle,
                metric_codes=["total_assets", "total_liab", "equity_parent"],
            ),
        ]

        warnings = self._build_dashboard_warnings(latest_metrics, same_period_metrics)
        source_notes = [
            BISourceNote(
                section="dashboard",
                statement_types=["income", "balance_sheet", "cashflow"],
                pit_rule="ann_date_before",
                metric_version="v1",
            )
        ]
        return BIDashboardResponse(
            symbol=symbol,
            as_of_date=self._to_api_date(as_of_date),
            latest_period=latest_period,
            company=company,
            kpis=kpis,
            trend_sections=trend_sections,
            summary_cards=summary_cards,
            warnings=warnings,
            source_notes=source_notes,
        )

    def get_company_dupont(
        self,
        *,
        symbol: str,
        as_of_date: str,
        market: str = "zh_a",
        source: str = "amazing_data",
    ) -> BIDupontResponse:
        bundle = self._load_bundle(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
        company = self._build_company_meta(bundle, symbol=symbol, market=market)
        latest_period = bundle.latest_period
        if not latest_period:
            raise ValueError(f"No financial data available for symbol={symbol}")

        latest_metrics = self._compute_snapshot_metrics(bundle, latest_period)
        same_period_metrics = self._compute_snapshot_metrics(bundle, self._same_period_last_year(latest_period))
        headline_codes = ["roe", "net_margin", "asset_turnover", "equity_multiplier"]
        headline_metrics = {
            code: self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
            for code in headline_codes
        }
        dupont_tree = BIDupontNode(
            code="roe",
            label="ROE",
            metric=headline_metrics["roe"],
            children=[
                BIDupontNode(code="net_margin", label="净利率", metric=headline_metrics["net_margin"]),
                BIDupontNode(code="asset_turnover", label="总资产周转率", metric=headline_metrics["asset_turnover"]),
                BIDupontNode(code="equity_multiplier", label="权益乘数", metric=headline_metrics["equity_multiplier"]),
            ],
        )

        periods = self._recent_common_periods(bundle.income, bundle.balance_sheet, limit=6)
        trend_sections = [
            self._build_trend_section("roe_trend", "ROE 多期趋势", periods, bundle, ["roe"]),
            self._build_trend_section("net_margin_trend", "净利率多期趋势", periods, bundle, ["net_margin"]),
            self._build_trend_section("asset_turnover_trend", "总资产周转率多期趋势", periods, bundle, ["asset_turnover"]),
            self._build_trend_section("equity_multiplier_trend", "权益乘数多期趋势", periods, bundle, ["equity_multiplier"]),
        ]

        driver_summary = self._build_dupont_driver_summary(latest_metrics, same_period_metrics)
        comparison_rows = [
            BIDupontComparisonRow(
                period=period,
                roe=self._compute_snapshot_metrics(bundle, period).get("roe"),
                net_margin=self._compute_snapshot_metrics(bundle, period).get("net_margin"),
                asset_turnover=self._compute_snapshot_metrics(bundle, period).get("asset_turnover"),
                equity_multiplier=self._compute_snapshot_metrics(bundle, period).get("equity_multiplier"),
            )
            for period in periods
        ]
        return BIDupontResponse(
            symbol=symbol,
            as_of_date=self._to_api_date(as_of_date),
            latest_period=latest_period,
            company=company,
            headline_metrics=headline_metrics,
            dupont_tree=dupont_tree,
            trend_sections=trend_sections,
            driver_summary=driver_summary,
            comparison_rows=comparison_rows,
        )

    def get_company_quality(
        self,
        *,
        symbol: str,
        as_of_date: str,
        market: str = "zh_a",
        source: str = "amazing_data",
    ) -> BIQualityResponse:
        bundle = self._load_bundle(symbol=symbol, as_of_date=as_of_date, market=market, source=source)
        company = self._build_company_meta(bundle, symbol=symbol, market=market)
        latest_period = bundle.latest_period
        if not latest_period:
            raise ValueError(f"No financial data available for symbol={symbol}")

        latest_metrics = self._compute_snapshot_metrics(bundle, latest_period)
        same_period_metrics = self._compute_snapshot_metrics(bundle, self._same_period_last_year(latest_period))
        periods = self._recent_common_periods(bundle.income, bundle.balance_sheet, limit=6)
        cashflow_periods = self._recent_common_periods(bundle.income, bundle.cashflow, limit=6)

        panels = [
            BIQualityPanel(
                code="operating_quality",
                title="经营利润质量",
                metrics=[
                    self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
                    for code in ["operating_profit_margin", "net_margin", "period_expense_ratio", "rd_expense_ratio", "ocf_to_profit"]
                ],
                trend_sections=[
                    self._build_trend_section(
                        "operating_quality_trend",
                        "利润率趋势",
                        periods,
                        bundle,
                        ["operating_profit_margin", "net_margin", "period_expense_ratio", "rd_expense_ratio"],
                    )
                ],
                table_rows=self._build_quality_rows(bundle, periods, ["operating_profit_margin", "net_margin", "period_expense_ratio", "rd_expense_ratio", "ocf_to_profit"]),
                warnings=self._build_operating_quality_warnings(latest_metrics, same_period_metrics),
            ),
            BIQualityPanel(
                code="cashflow_quality",
                title="现金流质量",
                metrics=[
                    self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
                    for code in ["operating_cashflow", "ocf_to_profit", "ocf_to_revenue", "free_cash_flow"]
                ],
                trend_sections=[
                    self._build_trend_section(
                        "cashflow_quality_trend",
                        "现金流趋势",
                        cashflow_periods,
                        bundle,
                        ["operating_cashflow", "net_profit_parent", "free_cash_flow"],
                    )
                ],
                table_rows=self._build_quality_rows(bundle, cashflow_periods, ["operating_cashflow", "ocf_to_profit", "ocf_to_revenue", "free_cash_flow"]),
                warnings=self._build_cashflow_warnings(latest_metrics, same_period_metrics),
            ),
            BIQualityPanel(
                code="turnover",
                title="资产周转",
                metrics=[
                    self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
                    for code in ["asset_turnover", "ar_turnover", "inventory_turnover"]
                ],
                trend_sections=[
                    self._build_trend_section(
                        "turnover_trend",
                        "效率趋势",
                        periods,
                        bundle,
                        ["asset_turnover", "ar_turnover", "inventory_turnover"],
                    )
                ],
                table_rows=self._build_quality_rows(bundle, periods, ["asset_turnover", "ar_turnover", "inventory_turnover"]),
                warnings=self._build_turnover_warnings(latest_metrics, same_period_metrics),
            ),
            BIQualityPanel(
                code="solvency",
                title="资产负债 / 偿债",
                metrics=[
                    self._make_metric_value(code, latest_metrics, same_period_metrics, latest_period)
                    for code in ["debt_ratio", "current_ratio", "quick_ratio", "currency_cap", "short_borrowing", "long_term_loan", "bonds_payable"]
                ],
                trend_sections=[
                    self._build_trend_section(
                        "solvency_trend",
                        "偿债与杠杆趋势",
                        periods,
                        bundle,
                        ["debt_ratio", "current_ratio", "quick_ratio", "currency_cap", "short_borrowing", "long_term_loan", "bonds_payable"],
                    )
                ],
                table_rows=self._build_quality_rows(bundle, periods, ["debt_ratio", "current_ratio", "quick_ratio", "currency_cap", "short_borrowing", "long_term_loan", "bonds_payable"]),
                warnings=self._build_solvency_warnings(latest_metrics, same_period_metrics),
            ),
        ]
        return BIQualityResponse(
            symbol=symbol,
            as_of_date=self._to_api_date(as_of_date),
            latest_period=latest_period,
            company=company,
            panels=panels,
            source_notes=[BISourceNote(section="quality", statement_types=["income", "balance_sheet", "cashflow"], pit_rule="ann_date_before", metric_version="v1")],
        )

    def _load_bundle(self, *, symbol: str, as_of_date: str, market: str, source: str) -> FinancialBundle:
        client = self._build_phoenix_client()
        security_map = client.get_securities(symbols=[symbol], market=market, asset_type="stock", limit=1)
        security = security_map.get(symbol, {})
        taxonomy = client.get_taxonomy_by_security(symbol)
        income = self._query_statement(client, symbol, market, source, "income", INCOME_FIELDS, as_of_date)
        balance_sheet = self._query_statement(client, symbol, market, source, "balance_sheet", BALANCE_FIELDS, as_of_date)
        cashflow = self._query_statement(client, symbol, market, source, "cashflow", CASHFLOW_FIELDS, as_of_date)
        latest_period = self._latest_period(balance_sheet, income, cashflow)
        return FinancialBundle(
            security=security,
            taxonomy=taxonomy,
            income=income,
            balance_sheet=balance_sheet,
            cashflow=cashflow,
            latest_period=latest_period,
        )

    def _build_phoenix_client(self) -> PhoenixAClient:
        dept = cfg_mgr.get_dept_services_for_source(None)
        if not dept or not dept.phoenixA:
            raise ValueError("phoenixA service not configured")
        cfg = dept.phoenixA
        return PhoenixAClient(
            host=cfg.host,
            port=cfg.port,
            logger=logger,
            timeout_seconds=getattr(cfg, "timeout_seconds", 30),
        )

    def _query_statement(
        self,
        client: PhoenixAClient,
        symbol: str,
        market: str,
        source: str,
        statement_type: str,
        data_fields: Iterable[str],
        as_of_date: str,
    ) -> List[Dict[str, Any]]:
        fields = COMMON_TOP_LEVEL_FIELDS + [f"data_json.{field}" for field in data_fields]
        response = client.query_financial_statements(
            source=source,
            statement_type=statement_type,
            symbol=symbol,
            market=market,
            ann_date_before=self._to_api_date(as_of_date),
            fields=fields,
            page=1,
            page_size=12,
        )
        rows = response.get("data", []) if isinstance(response, dict) else []
        normalized_rows: List[Dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            row = {k: v for k, v in item.items() if k != "data_json"}
            data_json = item.get("data_json") or {}
            if isinstance(data_json, dict):
                row.update(data_json)
            row["_period_norm"] = normalize_period(row.get("reporting_period"))
            normalized_rows.append(row)
        normalized_rows.sort(key=lambda item: item.get("_period_norm", ""), reverse=True)
        return normalized_rows

    def _build_company_meta(self, bundle: FinancialBundle, *, symbol: str, market: str) -> BICompanyMeta:
        chosen_taxonomy = self._pick_taxonomy(bundle.taxonomy)
        security = bundle.security or {}
        industry = BIIndustryMeta(
            taxonomy=str(chosen_taxonomy.get("canonical_taxonomy") or chosen_taxonomy.get("taxonomy") or ""),
            level=int(chosen_taxonomy.get("canonical_level") or chosen_taxonomy.get("level") or 0),
            code=str(chosen_taxonomy.get("canonical_category_code") or chosen_taxonomy.get("category_code") or ""),
            name=str(chosen_taxonomy.get("canonical_category_name") or chosen_taxonomy.get("category_name") or ""),
            index_code=str(chosen_taxonomy.get("canonical_index_code") or chosen_taxonomy.get("index_code") or ""),
        )
        financial_sector = bool((chosen_taxonomy.get("derived_flags") or {}).get("financial_sector", False))
        comp_type_code = self._resolve_comp_type_code(bundle)
        return BICompanyMeta(
            symbol=symbol,
            name=str(security.get("name") or self._first_non_empty(bundle.balance_sheet, "security_name") or self._first_non_empty(bundle.income, "security_name") or ""),
            market=str(security.get("market") or market),
            exchange=str(security.get("exchange") or ""),
            industry=industry,
            comp_type_code=comp_type_code,
            financial_sector=financial_sector,
        )

    def _resolve_comp_type_code(self, bundle: FinancialBundle) -> int:
        for rows in [bundle.balance_sheet, bundle.income, bundle.cashflow]:
            if rows and rows[0].get("comp_type_code") is not None:
                try:
                    return int(rows[0].get("comp_type_code") or 0)
                except Exception:
                    return 0
        return 0

    def _pick_taxonomy(self, mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not mappings:
            return {}
        for item in mappings:
            if int(item.get("canonical_level") or item.get("level") or 0) == 1:
                return item
        return mappings[0]

    def _latest_period(self, *statement_sets: List[Dict[str, Any]]) -> str:
        best = ""
        for rows in statement_sets:
            if rows:
                candidate = str(rows[0].get("reporting_period") or "")
                if normalize_period(candidate) > normalize_period(best):
                    best = candidate
        return best

    def _compute_snapshot_metrics(self, bundle: FinancialBundle, period: str) -> Dict[str, Optional[float]]:
        normalized_period = normalize_period(period)
        if not normalized_period:
            return {}

        income = self._find_record(bundle.income, normalized_period)
        balance = self._find_record(bundle.balance_sheet, normalized_period)
        cashflow = self._find_record(bundle.cashflow, normalized_period)
        prev_balance = self._previous_record(bundle.balance_sheet, normalized_period)

        revenue_total = self._to_float((income or {}).get("TOT_OPERA_REV"))
        operating_profit = self._to_float((income or {}).get("OPERA_PROFIT"))
        net_profit_parent = self._to_float((income or {}).get("NET_PRO_EXCL_MIN_INT_INC"))
        operating_cashflow = self._to_float((cashflow or {}).get("NET_CASH_FLOW_OPERA_ACT"))
        total_assets = self._to_float((balance or {}).get("TOTAL_ASSETS"))
        total_liab = self._to_float((balance or {}).get("TOTAL_LIAB"))
        equity_parent = self._to_float((balance or {}).get("TOT_SHARE_EQUITY_EXCL_MIN_INT"))
        current_assets = self._to_float((balance or {}).get("TOTAL_CUR_ASSETS"))
        current_liab = self._to_float((balance or {}).get("TOTAL_CUR_LIAB"))
        inventory = self._to_float((balance or {}).get("INV"))
        ar_value = self._to_float((balance or {}).get("ACCT_RECEIVABLE"))
        less_operating_cost = self._to_float((income or {}).get("LESS_OPERA_COST"))
        less_selling_exp = self._to_float((income or {}).get("LESS_SELLING_EXP"))
        less_admin_exp = self._to_float((income or {}).get("LESS_ADMIN_EXP"))
        less_fin_exp = self._to_float((income or {}).get("LESS_FIN_EXP"))
        rd_exp = self._to_float((income or {}).get("RD_EXP"))
        free_cash_flow = self._to_float((cashflow or {}).get("FREE_CASH_FLOW"))
        currency_cap = self._to_float((balance or {}).get("CURRENCY_CAP"))
        short_borrowing = self._to_float((balance or {}).get("ST_BORROWING"))
        long_term_loan = self._to_float((balance or {}).get("LT_LOAN"))
        bonds_payable = self._to_float((balance or {}).get("BONDS_PAYABLE"))

        avg_assets = self._average(total_assets, self._to_float((prev_balance or {}).get("TOTAL_ASSETS")))
        avg_equity = self._average(equity_parent, self._to_float((prev_balance or {}).get("TOT_SHARE_EQUITY_EXCL_MIN_INT")))
        avg_ar = self._average(ar_value, self._to_float((prev_balance or {}).get("ACCT_RECEIVABLE")))
        avg_inventory = self._average(inventory, self._to_float((prev_balance or {}).get("INV")))

        metrics: Dict[str, Optional[float]] = {
            "revenue_total": revenue_total,
            "operating_profit": operating_profit,
            "net_profit_parent": net_profit_parent,
            "operating_cashflow": operating_cashflow,
            "total_assets": total_assets,
            "total_liab": total_liab,
            "equity_parent": equity_parent,
            "currency_cap": currency_cap,
            "short_borrowing": short_borrowing,
            "long_term_loan": long_term_loan,
            "bonds_payable": bonds_payable,
            "debt_ratio": self._safe_div(total_liab, total_assets),
            "current_ratio": self._safe_div(current_assets, current_liab),
            "quick_ratio": self._safe_div(self._subtract(current_assets, inventory), current_liab),
            "roe": self._safe_div(net_profit_parent, avg_equity),
            "roa": self._safe_div(net_profit_parent, avg_assets),
            "net_margin": self._safe_div(net_profit_parent, revenue_total),
            "operating_profit_margin": self._safe_div(operating_profit, revenue_total),
            "asset_turnover": self._safe_div(revenue_total, avg_assets),
            "ar_turnover": self._safe_div(revenue_total, avg_ar),
            "inventory_turnover": self._safe_div(less_operating_cost, avg_inventory),
            "ocf_to_profit": self._safe_div(operating_cashflow, net_profit_parent),
            "ocf_to_revenue": self._safe_div(operating_cashflow, revenue_total),
            "free_cash_flow": free_cash_flow,
            "period_expense_ratio": self._safe_div(self._sum_values(less_selling_exp, less_admin_exp, less_fin_exp), revenue_total),
            "rd_expense_ratio": self._safe_div(rd_exp, revenue_total),
            "equity_multiplier": self._safe_div(avg_assets, avg_equity),
        }
        return metrics

    def _make_metric_value(
        self,
        code: str,
        current_metrics: Dict[str, Optional[float]],
        last_year_metrics: Dict[str, Optional[float]],
        data_period: str,
    ) -> BIMetricValue:
        meta = METRIC_DEFINITION_MAP[code]
        current_raw = current_metrics.get(code)
        last_year_raw = last_year_metrics.get(code)
        current_value = self._display_value(code, current_raw)
        same_period_last_year = self._display_value(code, last_year_raw)
        yoy_delta = self._display_delta(code, current_raw, last_year_raw)
        yoy_growth = self._display_growth(code, current_raw, last_year_raw)
        available = current_raw is not None
        degraded = False
        notes: List[str] = []
        if not available:
            degraded = True
            notes.append("metric_unavailable_for_current_period")
        elif code in {"ar_turnover", "inventory_turnover", "period_expense_ratio", "rd_expense_ratio", "free_cash_flow"} and current_raw is None:
            degraded = True
            notes.append("conditional_metric_unavailable")
        return BIMetricValue(
            code=code,
            label=meta["label"],
            unit=meta["unit"],
            display_kind=meta["display_kind"],
            value=current_value,
            same_period_last_year=same_period_last_year,
            yoy_delta=yoy_delta,
            yoy_growth=yoy_growth,
            data_period=data_period,
            source_fields=list(meta.get("source_fields") or []),
            available=available,
            degraded=degraded,
            notes=notes,
        )

    def _display_value(self, code: str, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if code in AMOUNT_METRIC_CODES:
            return round(value / 1e8, 4)
        return round(value, 6)

    def _display_delta(self, code: str, current: Optional[float], last_year: Optional[float]) -> Optional[float]:
        if current is None or last_year is None:
            return None
        return self._display_value(code, current - last_year)

    def _display_growth(self, code: str, current: Optional[float], last_year: Optional[float]) -> Optional[float]:
        if current is None or last_year in (None, 0):
            return None
        if METRIC_DEFINITION_MAP[code]["display_kind"] in {"ratio", "pct_point"}:
            return None
        return round((current - last_year) / abs(last_year), 6)

    def _build_trend_section(
        self,
        code: str,
        title: str,
        periods: List[str],
        bundle: FinancialBundle,
        metric_codes: List[str],
    ) -> BITrendSection:
        series: List[BITrendSeries] = []
        for metric_code in metric_codes:
            meta = METRIC_DEFINITION_MAP[metric_code]
            values = [
                self._display_value(metric_code, self._compute_snapshot_metrics(bundle, period).get(metric_code))
                for period in periods
            ]
            series.append(BITrendSeries(code=metric_code, label=meta["label"], values=values))
        return BITrendSection(code=code, title=title, periods=periods, series=series)

    def _build_dashboard_warnings(
        self,
        latest_metrics: Dict[str, Optional[float]],
        last_year_metrics: Dict[str, Optional[float]],
    ) -> List[BIWarning]:
        warnings: List[BIWarning] = []
        ocf = latest_metrics.get("operating_cashflow")
        np = latest_metrics.get("net_profit_parent")
        if ocf is not None and np is not None and ocf < np:
            warnings.append(BIWarning(code="ocf_weaker_than_profit", severity="medium", title="现金转化偏弱", message="经营现金流低于归母净利润", evidence_metric_codes=["operating_cashflow", "net_profit_parent"]))
        if (
            latest_metrics.get("operating_cashflow") is not None
            and last_year_metrics.get("operating_cashflow") is not None
            and latest_metrics.get("net_profit_parent") is not None
            and last_year_metrics.get("net_profit_parent") is not None
            and latest_metrics["operating_cashflow"] < last_year_metrics["operating_cashflow"]
            and latest_metrics["net_profit_parent"] > last_year_metrics["net_profit_parent"]
        ):
            warnings.append(BIWarning(code="cash_profit_divergence", severity="high", title="利润与现金背离", message="经营现金流同比下降而净利润同比上升", evidence_metric_codes=["operating_cashflow", "net_profit_parent"]))
        if (
            latest_metrics.get("debt_ratio") is not None
            and last_year_metrics.get("debt_ratio") is not None
            and latest_metrics["debt_ratio"] > last_year_metrics["debt_ratio"]
        ):
            warnings.append(BIWarning(code="debt_ratio_rising", severity="medium", title="杠杆抬升", message="资产负债率同比上升", evidence_metric_codes=["debt_ratio"]))
        if latest_metrics.get("current_ratio") is not None and latest_metrics["current_ratio"] < 1.0:
            warnings.append(BIWarning(code="low_current_ratio", severity="high", title="短期偿债压力", message="流动比率低于 1.0", evidence_metric_codes=["current_ratio"]))
        if (
            latest_metrics.get("asset_turnover") is not None
            and last_year_metrics.get("asset_turnover") is not None
            and latest_metrics["asset_turnover"] < last_year_metrics["asset_turnover"]
        ):
            warnings.append(BIWarning(code="asset_turnover_weaker", severity="medium", title="经营效率走弱", message="总资产周转率同比下降", evidence_metric_codes=["asset_turnover"]))
        return warnings

    def _build_dupont_driver_summary(
        self,
        latest_metrics: Dict[str, Optional[float]],
        last_year_metrics: Dict[str, Optional[float]],
    ) -> List[BIDriverSummaryItem]:
        items: List[BIDriverSummaryItem] = []
        candidates = {
            "net_margin": "利润率贡献为主要正向驱动",
            "asset_turnover": "资产使用效率是主要变化来源",
            "equity_multiplier": "杠杆变化放大了 ROE 波动",
        }
        deltas = {
            code: (latest_metrics.get(code) or 0) - (last_year_metrics.get(code) or 0)
            for code in candidates
            if latest_metrics.get(code) is not None and last_year_metrics.get(code) is not None
        }
        if not deltas:
            return [BIDriverSummaryItem(driver="n/a", direction="flat", message="暂无足够同比数据用于驱动解释")]
        ranked = sorted(deltas.items(), key=lambda item: abs(item[1]), reverse=True)
        for code, delta in ranked:
            direction: str = "flat"
            if delta > 0:
                direction = "up"
            elif delta < 0:
                direction = "down"
            items.append(
                BIDriverSummaryItem(
                    driver=code,
                    direction=direction,  # type: ignore[arg-type]
                    message=candidates[code],
                )
            )
        return items

    def _build_quality_rows(self, bundle: FinancialBundle, periods: List[str], metric_codes: List[str]) -> List[BIQualityTableRow]:
        rows: List[BIQualityTableRow] = []
        for period in periods:
            snapshot = self._compute_snapshot_metrics(bundle, period)
            rows.append(
                BIQualityTableRow(
                    period=period,
                    values={code: self._display_value(code, snapshot.get(code)) for code in metric_codes},
                )
            )
        return rows

    def _build_operating_quality_warnings(self, latest_metrics: Dict[str, Optional[float]], last_year_metrics: Dict[str, Optional[float]]) -> List[BIWarning]:
        warnings: List[BIWarning] = []
        if (
            latest_metrics.get("operating_profit_margin") is not None
            and last_year_metrics.get("operating_profit_margin") is not None
            and latest_metrics["operating_profit_margin"] < last_year_metrics["operating_profit_margin"]
        ):
            warnings.append(BIWarning(code="operating_margin_weaker", severity="medium", title="利润率走弱", message="营业利润率同比下降", evidence_metric_codes=["operating_profit_margin"]))
        if (
            latest_metrics.get("period_expense_ratio") is not None
            and last_year_metrics.get("period_expense_ratio") is not None
            and latest_metrics["period_expense_ratio"] > last_year_metrics["period_expense_ratio"]
        ):
            warnings.append(BIWarning(code="expense_ratio_rising", severity="medium", title="费用率抬升", message="期间费用率同比上升", evidence_metric_codes=["period_expense_ratio"]))
        return warnings

    def _build_cashflow_warnings(self, latest_metrics: Dict[str, Optional[float]], last_year_metrics: Dict[str, Optional[float]]) -> List[BIWarning]:
        warnings: List[BIWarning] = []
        if latest_metrics.get("ocf_to_profit") is not None and latest_metrics["ocf_to_profit"] < 1:
            warnings.append(BIWarning(code="low_ocf_to_profit", severity="medium", title="利润现金含量偏弱", message="OCF/净利润低于 1", evidence_metric_codes=["ocf_to_profit"]))
        if (
            latest_metrics.get("free_cash_flow") is not None
            and latest_metrics["free_cash_flow"] < 0
        ):
            warnings.append(BIWarning(code="negative_fcf", severity="medium", title="自由现金流为负", message="自由现金流为负，需关注资本开支与回款节奏", evidence_metric_codes=["free_cash_flow"]))
        return warnings

    def _build_turnover_warnings(self, latest_metrics: Dict[str, Optional[float]], last_year_metrics: Dict[str, Optional[float]]) -> List[BIWarning]:
        warnings: List[BIWarning] = []
        for code, title in [("asset_turnover", "总资产周转率"), ("ar_turnover", "应收账款周转率"), ("inventory_turnover", "存货周转率")]:
            if (
                latest_metrics.get(code) is not None
                and last_year_metrics.get(code) is not None
                and latest_metrics[code] < last_year_metrics[code]
            ):
                warnings.append(BIWarning(code=f"{code}_weaker", severity="medium", title=f"{title}走弱", message=f"{title}同比下降", evidence_metric_codes=[code]))
        return warnings

    def _build_solvency_warnings(self, latest_metrics: Dict[str, Optional[float]], last_year_metrics: Dict[str, Optional[float]]) -> List[BIWarning]:
        warnings: List[BIWarning] = []
        if latest_metrics.get("quick_ratio") is not None and latest_metrics["quick_ratio"] < 1:
            warnings.append(BIWarning(code="low_quick_ratio", severity="medium", title="速动性偏弱", message="速动比率低于 1", evidence_metric_codes=["quick_ratio"]))
        if (
            latest_metrics.get("short_borrowing") is not None
            and last_year_metrics.get("short_borrowing") is not None
            and latest_metrics["short_borrowing"] > last_year_metrics["short_borrowing"]
        ):
            warnings.append(BIWarning(code="short_debt_rising", severity="medium", title="短债压力抬升", message="短期借款同比增加", evidence_metric_codes=["short_borrowing"]))
        return warnings

    def _resolve_peer_symbols(self, req: BIPeerComparisonRequest) -> List[str]:
        symbols = [str(item).strip() for item in (req.symbols or []) if str(item).strip()]
        if symbols:
            return list(dict.fromkeys(symbols))[: max(1, req.limit)]

        if not req.industry_code:
            return []

        client = self._build_phoenix_client()
        response = client.query_industry_constituents_by_index(
            source=req.source,
            taxonomy="",
            market=req.market,
            index_code=req.industry_code,
            page=1,
            page_size=max(req.limit, 100),
        )
        rows = response.get("list") or response.get("data") or []
        extracted: List[str] = []
        for row in rows:
            symbol = self._extract_symbol_from_constituent(row)
            if symbol:
                extracted.append(symbol)
        return list(dict.fromkeys(extracted))[: max(1, req.limit)]

    @staticmethod
    def _extract_symbol_from_constituent(row: Any) -> str:
        if not isinstance(row, dict):
            return ""
        for key in ["symbol", "con_code", "security_code", "code"]:
            value = str(row.get(key) or "").strip()
            if value:
                return value
        return ""

    def _build_structured_highlights(
        self,
        latest_metrics: Dict[str, Optional[float]],
        last_year_metrics: Dict[str, Optional[float]],
    ) -> List[BIInsightHighlight]:
        highlights: List[BIInsightHighlight] = []
        metric_messages = {
            "revenue_total": "营业总收入同比变化",
            "operating_profit": "营业利润同比变化",
            "net_profit_parent": "归母净利润同比变化",
            "operating_cashflow": "经营现金流同比变化",
            "debt_ratio": "资产负债率同比变化",
            "asset_turnover": "总资产周转率同比变化",
            "ocf_to_profit": "利润现金含量变化",
        }
        for code in DEFAULT_INSIGHT_METRIC_CODES:
            current = latest_metrics.get(code)
            previous = last_year_metrics.get(code)
            if current is None or previous is None:
                continue
            delta = current - previous
            if abs(delta) < 1e-9:
                continue
            highlights.append(
                BIInsightHighlight(
                    code=code,
                    title=metric_messages.get(code, code),
                    message=self._format_metric_change_message(code, current, previous),
                    related_metrics=[code],
                )
            )
        if not highlights:
            highlights.append(
                BIInsightHighlight(
                    code="no_change_detected",
                    title="暂无显著变化",
                    message="当前可得结构化指标不足以形成显著摘要，请结合详细看板查看。",
                    related_metrics=[],
                )
            )
        return highlights[:6]

    def _build_insight_trend_summary(
        self,
        latest_metrics: Dict[str, Optional[float]],
        last_year_metrics: Dict[str, Optional[float]],
    ) -> List[str]:
        summary: List[str] = []
        for code in ["revenue_total", "net_profit_parent", "operating_cashflow", "debt_ratio", "asset_turnover"]:
            current = latest_metrics.get(code)
            previous = last_year_metrics.get(code)
            if current is None or previous is None:
                continue
            summary.append(self._format_metric_change_message(code, current, previous))
        return summary[:5]

    def _format_metric_change_message(self, code: str, current: float, previous: float) -> str:
        label = str(METRIC_DEFINITION_MAP.get(code, {}).get("label") or code)
        if code in AMOUNT_METRIC_CODES:
            current_display = self._display_value(code, current)
            previous_display = self._display_value(code, previous)
            growth = self._display_growth(code, current, previous)
            if growth is None:
                return f"{label}当前为 {current_display:.2f}，去年同期为 {previous_display:.2f}。"
            return f"{label}当前为 {current_display:.2f}，去年同期为 {previous_display:.2f}，同比 {(growth * 100):.2f}%。"

        delta = self._display_delta(code, current, previous)
        current_display = self._display_value(code, current)
        previous_display = self._display_value(code, previous)
        if delta is None:
            return f"{label}当前为 {current_display:.4f}，去年同期为 {previous_display:.4f}。"
        return f"{label}当前为 {current_display:.4f}，去年同期为 {previous_display:.4f}，同比变动 {delta:.4f}。"

    def _find_record(self, rows: List[Dict[str, Any]], period: str) -> Optional[Dict[str, Any]]:
        normalized_period = normalize_period(period)
        for row in rows:
            if row.get("_period_norm") == normalized_period:
                return row
        return None

    def _previous_record(self, rows: List[Dict[str, Any]], period: str) -> Optional[Dict[str, Any]]:
        normalized_period = normalize_period(period)
        for index, row in enumerate(rows):
            if row.get("_period_norm") == normalized_period:
                if index + 1 < len(rows):
                    return rows[index + 1]
                return None
        return None

    def _recent_periods(self, rows: List[Dict[str, Any]], *, limit: int) -> List[str]:
        return [str(row.get("reporting_period") or "") for row in rows[:limit]]

    def _recent_common_periods(self, first: List[Dict[str, Any]], second: List[Dict[str, Any]], *, limit: int) -> List[str]:
        second_periods = {row.get("_period_norm") for row in second}
        periods = [str(row.get("reporting_period") or "") for row in first if row.get("_period_norm") in second_periods]
        return periods[:limit]

    def _same_period_last_year(self, period: str) -> str:
        normalized = normalize_period(period)
        if len(normalized) != 8:
            return ""
        return f"{int(normalized[:4]) - 1}{normalized[4:]}"

    def _first_non_empty(self, rows: List[Dict[str, Any]], key: str) -> str:
        for row in rows:
            value = str(row.get(key) or "")
            if value:
                return value
        return ""

    @staticmethod
    def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        if numerator is None or denominator in (None, 0):
            return None
        return numerator / denominator

    @staticmethod
    def _average(first: Optional[float], second: Optional[float]) -> Optional[float]:
        if first is None and second is None:
            return None
        if first is None:
            return second
        if second is None:
            return first
        return (first + second) / 2

    @staticmethod
    def _sum_values(*values: Optional[float]) -> Optional[float]:
        usable = [value for value in values if value is not None]
        if not usable:
            return None
        return sum(usable)

    @staticmethod
    def _subtract(first: Optional[float], second: Optional[float]) -> Optional[float]:
        if first is None or second is None:
            return None
        return first - second

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _to_api_date(value: str) -> str:
        normalized = normalize_date(value)
        if len(normalized) == 8:
            return f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}"
        return value






