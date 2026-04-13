package model

type Category struct{}

// ========================== Models ==========================
// 申万行业 分类
type CategorySWHY struct {
	Category
	IndexCode    string `gorm:"type:varchar(9);not null" json:"index_code"`
	IndustryCode string `gorm:"type:varchar(6);not null;unique" json:"industry_code"`
	LevelType    uint8  `gorm:"type:tinyint unsigned;not null" json:"level_type"`
	Level1Name   string `gorm:"type:varchar(16);not null" json:"level1_name"`
	Level2Name   string `gorm:"type:varchar(16);not null" json:"level2_name"`
	Level3Name   string `gorm:"type:varchar(16);not null" json:"level3_name"`
	IsPub        uint8  `gorm:"type:tinyint unsigned;not null" json:"is_pub"`
	ChangeReason string `gorm:"type:varchar(32);not null;default:''" json:"change_reason"`
}

func (CategorySWHY) TableName() string { return "mkt_category_swhy" }

type CategoryMairui struct {
	Code       string  `gorm:"primaryKey;type:varchar(64);not null;unique" json:"code"`
	Name       string  `gorm:"type:varchar(255);not null" json:"name"`
	ParentCode *string `gorm:"type:varchar(64)" json:"parent_code"`
	ParentName *string `gorm:"type:varchar(255)" json:"parent_name"`
	Level      uint8   `gorm:"type:tinyint unsigned;not null" json:"level"`
	Type1      uint8   `gorm:"type:tinyint unsigned;not null" json:"type1"`
	Type2      uint16  `gorm:"type:smallint unsigned;not null" json:"type2"`
	IsLeaf     bool    `gorm:"type:tinyint(1);not null" json:"is_leaf"`
}

func (CategoryMairui) TableName() string { return "mkt_category_mairui" }

// ========================== Filters ==========================
type CategoryFiltersMairui struct {
	ParentName *string
	ParentCode *string // Exact match
	Level      *uint8  // Exact match
	Type1      *uint8  // Exact match
	Type2      *uint16 // Exact match
}

type CategoryFiltersSWHY struct {
	IndexCode    *string
	IndustryCode *string
	LevelType    *uint8
	Level1Name   *string
	Level2Name   *string
	Level3Name   *string
	IsPub        *uint8
}
