package model

import "encoding/json"

// SecurityEvent is minimal PIT metadata for announcements and disclosure dates.
type SecurityEvent struct {
	ID         uint64          `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	SecurityID uint64          `gorm:"column:security_id;not null;uniqueIndex:uk_security_event;index:idx_se_security_date" json:"security_id"`
	Source     string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_security_event" json:"source"`
	EventType  string          `gorm:"column:event_type;type:varchar(32);not null;uniqueIndex:uk_security_event;index:idx_se_type_date" json:"event_type"`
	EventDate  string          `gorm:"column:event_date;type:date;not null;uniqueIndex:uk_security_event;index:idx_se_security_date;index:idx_se_type_date" json:"event_date"`
	Title      string          `gorm:"type:varchar(512);not null;uniqueIndex:uk_security_event" json:"title"`
	URL        string          `gorm:"column:url;type:text" json:"url,omitempty"`
	DataJSON   json.RawMessage `gorm:"column:data_json;type:jsonb;not null;default:'{}'" json:"data_json"`
}

func (SecurityEvent) TableName() string { return "ods.security_event" }

type SecurityEventFilters struct {
	SecurityID  uint64
	SecurityIDs []uint64
	StartDate   string
	EndDate     string
	Title       string
}

type SecurityEventLastUpdate struct {
	SecurityID uint64 `gorm:"column:security_id" json:"security_id"`
	LastUpdate string `gorm:"column:last_update" json:"last_update"`
}
