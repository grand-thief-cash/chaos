package dao

import (
	"context"
	"fmt"

	"gorm.io/gorm"
)

func applyDateRange(q *gorm.DB, startDate, endDate string) *gorm.DB {
	if startDate != "" {
		q = q.Where("trade_date >= ?", startDate)
	}
	if endDate != "" {
		q = q.Where("trade_date <= ?", endDate)
	}
	return q
}

func finishDailyDataQuery(q *gorm.DB, limit, offset int) *gorm.DB {
	q = q.Order("trade_date ASC")
	if limit > 0 {
		q = q.Limit(limit)
	}
	if offset > 0 {
		q = q.Offset(offset)
	}
	return q
}

type keyedLastUpdate struct {
	Key        string `gorm:"column:key"`
	LastUpdate string `gorm:"column:last_update"`
}

func lastUpdatesByStringKey(
	ctx context.Context,
	db *gorm.DB,
	tableModel any,
	keyColumn string,
	keys []string,
) (map[string]string, error) {
	var rows []keyedLastUpdate
	q := db.WithContext(ctx).Model(tableModel).
		Select(fmt.Sprintf(
			"%s AS key, MAX(trade_date)::text AS last_update", keyColumn,
		)).
		Group(keyColumn)
	if len(keys) > 0 {
		q = q.Where(fmt.Sprintf("%s IN ?", keyColumn), keys)
	}
	if err := q.Scan(&rows).Error; err != nil {
		return nil, err
	}
	result := make(map[string]string, len(rows))
	for _, row := range rows {
		result[row.Key] = row.LastUpdate
	}
	return result, nil
}
