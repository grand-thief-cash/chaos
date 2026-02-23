package service

import (
	"context"
	"encoding/json"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
)

type IMarketCategoryService[T any, F any] interface {
	Create(ctx context.Context, data *T) error
	Update(ctx context.Context, data *T) error
	BatchUpsert(ctx context.Context, data []*T) error
	Get(ctx context.Context, code string) (*T, error)
	Delete(ctx context.Context, code string) error
	List(ctx context.Context, filter *F, page, pageSize int) ([]*T, int64, error)
}

type IMarketHistService[T any, F any] interface {
	core.Component
	BatchUpsert(ctx context.Context, req *F, data json.RawMessage) error
	GetLatestUpdateByCodes(ctx context.Context, req *F) (map[string]string, error)
	GetStockHist(ctx context.Context, req *F) ([]*T, error) // GetStockHist returns daily bars for a single code within [startDate, endDate], selecting only requested fields.
}
