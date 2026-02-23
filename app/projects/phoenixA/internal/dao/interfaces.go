package dao

import (
	"context"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type IMarketCategoryDao[T any, F any] interface {
	Create(ctx context.Context, m *T) error
	Update(ctx context.Context, m *T) error
	BatchUpsert(ctx context.Context, list []*T, chunkSize int) error
	Get(ctx context.Context, code string) (*T, error)
	Delete(ctx context.Context, code string) error
	List(ctx context.Context, filters *F, limit, offset int) ([]*T, error)
	Count(ctx context.Context, filters *F) (int64, error)
}

type IStockZhAHistDao[T any, F any] interface {
	core.Component
	BatchUpsert(ctx context.Context, req *F, data []*T) error
	GetLatestUpdateByCodes(ctx context.Context, req *F) (map[string]string, error)
	GetStockHist(ctx context.Context, req *F) ([]*T, error) // GetStockHist returns daily bars for a single code within [startDate, endDate], selecting only requested fields.
}
