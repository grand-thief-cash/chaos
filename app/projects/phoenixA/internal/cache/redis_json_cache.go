package cache

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	redislib "github.com/redis/go-redis/v9"
)

func GetJSON[T any](ctx context.Context, client redislib.UniversalClient, key string) (T, bool, error) {
	var zero T
	if client == nil || key == "" {
		return zero, false, nil
	}

	payload, err := client.Get(ctx, key).Bytes()
	if err != nil {
		if errors.Is(err, redislib.Nil) {
			return zero, false, nil
		}
		return zero, false, err
	}

	var out T
	if err := json.Unmarshal(payload, &out); err != nil {
		return zero, false, err
	}
	return out, true, nil
}

func SetJSON(ctx context.Context, client redislib.UniversalClient, key string, ttl time.Duration, value any) error {
	if client == nil || key == "" || ttl <= 0 {
		return nil
	}
	payload, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return client.Set(ctx, key, payload, ttl).Err()
}

func DeleteKeys(ctx context.Context, client redislib.UniversalClient, keys ...string) error {
	if client == nil {
		return nil
	}
	filtered := make([]string, 0, len(keys))
	for _, key := range keys {
		if key != "" {
			filtered = append(filtered, key)
		}
	}
	if len(filtered) == 0 {
		return nil
	}
	return client.Del(ctx, filtered...).Err()
}

func DeleteByPattern(ctx context.Context, client redislib.UniversalClient, pattern string) error {
	if client == nil || pattern == "" {
		return nil
	}
	var cursor uint64
	for {
		keys, nextCursor, err := client.Scan(ctx, cursor, pattern, 200).Result()
		if err != nil {
			return err
		}
		if len(keys) > 0 {
			if err := client.Del(ctx, keys...).Err(); err != nil {
				return err
			}
		}
		cursor = nextCursor
		if cursor == 0 {
			break
		}
	}
	return nil
}
