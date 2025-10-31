package service

import (
	"context"
	"fmt"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/cronjob/internal/consts"
)

// CallbackTimeoutScanner 定期扫描 callback_deadline 已过期且仍为 CALLBACK_PENDING 的运行，标记 FAILED_TIMEOUT。
// 轻量实现：默认 30s 周期，每次最多处理 500 条。

type CallbackTimeoutScanner struct {
	*core.BaseComponent
	RunSvc   *RunService         `infra:"dep:run_service"`
	Progress *RunProgressManager `infra:"dep:run_progress_mgr"`
	interval time.Duration
	cancel   context.CancelFunc
}

func NewCallbackTimeoutScanner(interval time.Duration) *CallbackTimeoutScanner {
	if interval <= 0 {
		interval = 30 * time.Second
	}
	return &CallbackTimeoutScanner{BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_CALLBACK_SCANNER), interval: interval}
}

func (c *CallbackTimeoutScanner) Start(ctx context.Context) error {
	if c.IsActive() {
		return nil
	}
	if err := c.BaseComponent.Start(ctx); err != nil {
		return err
	}
	loopCtx, cancel := context.WithCancel(context.Background())
	c.cancel = cancel
	go c.loop(loopCtx)
	return nil
}

func (c *CallbackTimeoutScanner) Stop(ctx context.Context) error {
	if !c.IsActive() {
		return nil
	}
	if c.cancel != nil {
		c.cancel()
	}
	return c.BaseComponent.Stop(ctx)
}

func (c *CallbackTimeoutScanner) loop(ctx context.Context) {
	ticker := time.NewTicker(c.interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			c.scan(ctx)
		}
	}
}

func (c *CallbackTimeoutScanner) scan(ctx context.Context) {
	expired, err := c.RunSvc.ListCallbackPendingExpired(ctx, 500)
	if err != nil {
		logging.Error(ctx, "callback scanner list expired failed: "+err.Error())
		return
	}
	for _, run := range expired {
		if err := c.RunSvc.MarkFailedTimeout(ctx, run.ID, "callback_deadline_exceeded"); err != nil {
			logging.Error(ctx, "mark failed timeout run="+err.Error())
			continue
		}
		if c.Progress != nil {
			c.Progress.Clear(run.ID)
		}
		logging.Info(ctx, fmt.Sprintf("callback deadline exceeded run_id=%d", run.ID))
	}
}
