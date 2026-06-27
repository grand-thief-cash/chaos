package dao

import (
	"context"
	"fmt"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// rawCoverageRow is the scan target for per-symbol coverage queries.
// report_type is empty for corporate_action and equity_structure.
type rawCoverageRow struct {
	Source         string
	Dataset        string
	DataType       string
	ReportType     string
	RowCount       int64
	EarliestPeriod string
	LatestPeriod   string
	LatestAnnDate  string
}

// GetSymbolCoverage returns per-dataset/data_type row counts and time ranges
// for a given symbol+market across financial_statement, corporate_action, and
// equity_structure. This is a generic discovery query — callers aggregate
// further as needed.
func (d *CatalogDao) GetSymbolCoverage(ctx context.Context, symbol, market string) ([]rawCoverageRow, error) {
	if symbol == "" {
		return nil, fmt.Errorf("symbol is required")
	}
	if market == "" {
		market = "zh_a"
	}

	var rows []rawCoverageRow

	// financial_statement: group by (source, statement_type, report_type)
	fsQuery := `
		SELECT
			source,
			'financial_statement' AS dataset,
			statement_type AS data_type,
			COALESCE(report_type, '') AS report_type,
			COUNT(*) AS row_count,
			COALESCE(MIN(reporting_period), '') AS earliest_period,
			COALESCE(MAX(reporting_period), '') AS latest_period,
			COALESCE(MAX(ann_date), '') AS latest_ann_date
		FROM financial_statement
		WHERE symbol = $1 AND market = $2
		GROUP BY source, statement_type, report_type
		ORDER BY source, statement_type, report_type
	`
	var fsRows []rawCoverageRow
	if err := d.db.WithContext(ctx).Raw(fsQuery, symbol, market).Scan(&fsRows).Error; err != nil {
		return nil, fmt.Errorf("query financial_statement coverage: %w", err)
	}
	rows = append(rows, fsRows...)

	// corporate_action: group by (source, action_type)
	caQuery := `
		SELECT
			source,
			'corporate_action' AS dataset,
			action_type AS data_type,
			'' AS report_type,
			COUNT(*) AS row_count,
			COALESCE(MIN(report_period), '') AS earliest_period,
			COALESCE(MAX(report_period), '') AS latest_period,
			COALESCE(MAX(ann_date), '') AS latest_ann_date
		FROM corporate_action
		WHERE symbol = $1 AND market = $2
		GROUP BY source, action_type
		ORDER BY source, action_type
	`
	var caRows []rawCoverageRow
	if err := d.db.WithContext(ctx).Raw(caQuery, symbol, market).Scan(&caRows).Error; err != nil {
		return nil, fmt.Errorf("query corporate_action coverage: %w", err)
	}
	rows = append(rows, caRows...)

	// equity_structure: single data_type, group by source
	esQuery := `
		SELECT
			source,
			'equity_structure' AS dataset,
			'equity_structure' AS data_type,
			'' AS report_type,
			COUNT(*) AS row_count,
			COALESCE(MIN(change_date), '') AS earliest_period,
			COALESCE(MAX(change_date), '') AS latest_period,
			COALESCE(MAX(ann_date), '') AS latest_ann_date
		FROM equity_structure
		WHERE symbol = $1 AND market = $2
		GROUP BY source
		ORDER BY source
	`
	var esRows []rawCoverageRow
	if err := d.db.WithContext(ctx).Raw(esQuery, symbol, market).Scan(&esRows).Error; err != nil {
		return nil, fmt.Errorf("query equity_structure coverage: %w", err)
	}
	rows = append(rows, esRows...)

	return rows, nil
}

// AggregateCoverage converts flat rawCoverageRow slices into the hierarchical
// CatalogSymbolCoverage response, grouping by dataset then data_type, and
// nesting by_report_type for financial_statement.
func AggregateCoverage(rows []rawCoverageRow, symbol, market string) *model.CatalogSymbolCoverage {
	type dtypeKey struct {
		dataset  string
		source   string
		dataType string
	}
	dtypeAgg := map[dtypeKey]*model.CatalogDataTypeCoverage{}
	dtypeOrder := []dtypeKey{}

	// dataset order: financial_statement, corporate_action, equity_structure
	order := map[string]int{
		"financial_statement": 0,
		"corporate_action":    1,
		"equity_structure":    2,
	}

	for _, r := range rows {
		k := dtypeKey{dataset: r.Dataset, source: r.Source, dataType: r.DataType}
		agg, ok := dtypeAgg[k]
		if !ok {
			agg = &model.CatalogDataTypeCoverage{
				DataType:       r.DataType,
				EarliestPeriod: r.EarliestPeriod,
				LatestPeriod:   r.LatestPeriod,
				LatestAnnDate:  r.LatestAnnDate,
			}
			dtypeAgg[k] = agg
			dtypeOrder = append(dtypeOrder, k)
		}
		agg.TotalRows += int(r.RowCount)
		// widen time range across buckets
		if r.EarliestPeriod != "" && (agg.EarliestPeriod == "" || r.EarliestPeriod < agg.EarliestPeriod) {
			agg.EarliestPeriod = r.EarliestPeriod
		}
		if r.LatestPeriod != "" && r.LatestPeriod > agg.LatestPeriod {
			agg.LatestPeriod = r.LatestPeriod
		}
		if r.LatestAnnDate != "" && r.LatestAnnDate > agg.LatestAnnDate {
			agg.LatestAnnDate = r.LatestAnnDate
		}
		// For financial_statement, nest by report_type
		if r.Dataset == "financial_statement" && r.ReportType != "" {
			agg.ByReportType = append(agg.ByReportType, model.CatalogReportTypeBucket{
				ReportType:     r.ReportType,
				RowCount:       int(r.RowCount),
				EarliestPeriod: r.EarliestPeriod,
				LatestPeriod:   r.LatestPeriod,
				LatestAnnDate:  r.LatestAnnDate,
			})
		}
	}

	// Group data_types under datasets, preserving dataset order.
	type dsKey struct {
		dataset string
		source  string
	}
	dsAgg := map[dsKey]*model.CatalogDatasetCoverage{}
	dsOrder := []dsKey{}
	for _, k := range dtypeOrder {
		dk := dsKey{dataset: k.dataset, source: k.source}
		ds, ok := dsAgg[dk]
		if !ok {
			ds = &model.CatalogDatasetCoverage{Dataset: k.dataset, Source: k.source}
			dsAgg[dk] = ds
			dsOrder = append(dsOrder, dk)
		}
		ds.DataTypes = append(ds.DataTypes, *dtypeAgg[k])
	}

	// Sort dsOrder by dataset order then source (insertion sort; N <= 3).
	for i := 1; i < len(dsOrder); i++ {
		for j := i; j > 0; j-- {
			a, b := dsOrder[j-1], dsOrder[j]
			oa, ob := order[a.dataset], order[b.dataset]
			if oa < ob || (oa == ob && a.source <= b.source) {
				break
			}
			dsOrder[j-1], dsOrder[j] = dsOrder[j], dsOrder[j-1]
		}
	}

	out := &model.CatalogSymbolCoverage{
		Symbol: symbol,
		Market: market,
	}
	for _, dk := range dsOrder {
		out.Datasets = append(out.Datasets, *dsAgg[dk])
	}
	return out
}
