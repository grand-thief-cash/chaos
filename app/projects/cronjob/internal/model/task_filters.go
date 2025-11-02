package model

import "time"

// TaskListFilters represents optional filters for listing tasks.
// Zero values / nil pointers mean filter not applied.
// NameLike / DescriptionLike are fuzzy (wrapped with %% automatically).
// Time ranges support independent from/to; if both provided a BETWEEN is used.
// All times assumed UTC unless provided with timezone offset.
// Acceptable input formats handled upstream (RFC3339 etc.).
// This struct lives in model for reuse by dao/service/api layers.

type TaskListFilters struct {
	Status          string
	NameLike        string
	DescriptionLike string
	CreatedFrom     *time.Time
	CreatedTo       *time.Time
	UpdatedFrom     *time.Time
	UpdatedTo       *time.Time
}
