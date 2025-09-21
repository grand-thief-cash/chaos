package http_client

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
)

type InstrumentedClient struct {
	Name           string
	BaseURL        string
	DefaultHeaders map[string]string
	Client         *http.Client
	Retry          *RetryConfig
	Underlying     *http.Transport // added
}

func (ic *InstrumentedClient) buildURL(path string, q map[string]string) (string, error) {
	if strings.HasPrefix(path, "http://") || strings.HasPrefix(path, "https://") {
		u, err := url.Parse(path)
		if err != nil {
			return "", err
		}
		if q != nil {
			qs := u.Query()
			for k, v := range q {
				qs.Set(k, v)
			}
			u.RawQuery = qs.Encode()
		}
		return u.String(), nil
	}

	base := ic.BaseURL
	if base == "" {
		base = ""
	}
	if path != "" && path[0] != '/' {
		path = "/" + path
	}
	full := base + path
	u, err := url.Parse(full)
	if err != nil {
		return "", err
	}
	if q != nil {
		qs := u.Query()
		for k, v := range q {
			qs.Set(k, v)
		}
		u.RawQuery = qs.Encode()
	}
	return u.String(), nil
}

func (ic *InstrumentedClient) Do(ctx context.Context, method, path string, query map[string]string, headers map[string]string, body interface{}, out interface{}) (*http.Response, error) {
	if method == "" {
		method = http.MethodGet
	}

	targetURL, err := ic.buildURL(path, query)
	if err != nil {
		return nil, err
	}

	var reqBody io.Reader
	var contentType string

	switch b := body.(type) {
	case nil:
	case io.Reader:
		reqBody = b
	case []byte:
		reqBody = bytes.NewReader(b)
	case string:
		reqBody = strings.NewReader(b)
	default:
		buf, errM := json.Marshal(b)
		if errM != nil {
			return nil, fmt.Errorf("marshal body: %w", errM)
		}
		reqBody = bytes.NewReader(buf)
		contentType = "application/json"
	}

	req, err := http.NewRequestWithContext(ctx, method, targetURL, reqBody)
	if err != nil {
		return nil, err
	}

	// Merge headers
	for k, v := range ic.DefaultHeaders {
		req.Header.Set(k, v)
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	if contentType != "" && req.Header.Get("Content-Type") == "" {
		req.Header.Set("Content-Type", contentType)
	}
	if req.Header.Get("Accept") == "" {
		req.Header.Set("Accept", "application/json, */*")
	}

	start := time.Now()
	resp, err := ic.doWithRetry(ctx, req)
	latency := time.Since(start)

	fields := []zap.Field{
		zap.String("client", ic.Name),
		zap.String("method", method),
		zap.String("url", targetURL),
		zap.Duration("latency", latency),
	}
	if err != nil {
		fields = append(fields, zap.String("error", err.Error()))
		logging.Error(ctx, "http_client_request", fields...)
		return resp, err
	}
	fields = append(fields, zap.Int("status", resp.StatusCode))
	logging.Info(ctx, "http_client_request", fields...)

	defer func() {
		// Ensure body drained if not read externally
		if out == nil {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
	}()

	if resp.StatusCode >= 400 {
		// Read limited body for error context
		slurp, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return resp, fmt.Errorf("http error status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(slurp)))
	}

	if out != nil {
		ct := resp.Header.Get("Content-Type")
		if strings.Contains(ct, "json") {
			dec := json.NewDecoder(resp.Body)
			if err := dec.Decode(out); err != nil && !errors.Is(err, io.EOF) {
				return resp, fmt.Errorf("decode response: %w", err)
			}
		} else {
			// If not JSON, try to read raw into *[]byte or *string
			raw, _ := io.ReadAll(resp.Body)
			switch o := out.(type) {
			case *[]byte:
				*o = raw
			case *string:
				*o = string(raw)
			default:
				// no-op: unsupported type for non-json
			}
		}
	}

	return resp, nil
}

func (ic *InstrumentedClient) Get(ctx context.Context, path string, query map[string]string, headers map[string]string, out interface{}) (*http.Response, error) {
	return ic.Do(ctx, http.MethodGet, path, query, headers, nil, out)
}

func (ic *InstrumentedClient) Post(ctx context.Context, path string, body interface{}, headers map[string]string, out interface{}) (*http.Response, error) {
	return ic.Do(ctx, http.MethodPost, path, nil, headers, body, out)
}

func (ic *InstrumentedClient) doWithRetry(ctx context.Context, req *http.Request) (*http.Response, error) {
	if ic.Retry == nil || !ic.Retry.Enabled || ic.Retry.MaxAttempts <= 1 {
		return ic.Client.Do(req)
	}

	backoff := ic.Retry.InitialBackoff
	var lastErr error
	for attempt := 1; attempt <= ic.Retry.MaxAttempts; attempt++ {
		resp, err := ic.Client.Do(req)
		if err == nil && resp.StatusCode < 500 {
			return resp, nil
		}
		if err == nil {
			// 5xx
			lastErr = fmt.Errorf("server error %d", resp.StatusCode)
			resp.Body.Close()
		} else {
			lastErr = err
		}

		// Decide whether to retry
		if attempt == ic.Retry.MaxAttempts {
			break
		}
		// Only retry on transient network errors or >=500
		if nErr, ok := lastErr.(net.Error); ok && !nErr.Temporary() && !nErr.Timeout() && (resp == nil || resp.StatusCode < 500) {
			break
		}

		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(backoff):
		}
		backoff = time.Duration(float64(backoff) * ic.Retry.BackoffMultiplier)
		if backoff > ic.Retry.MaxBackoff {
			backoff = ic.Retry.MaxBackoff
		}
	}
	return nil, lastErr
}
