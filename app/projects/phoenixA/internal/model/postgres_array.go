package model

import (
	"database/sql/driver"
	"fmt"
)

// StringArray is shared PostgreSQL TEXT[] plumbing used by catalog scans.
type StringArray []string

func (a StringArray) Value() (driver.Value, error) {
	if a == nil {
		return "{}", nil
	}
	result := "{"
	for i, value := range a {
		if i > 0 {
			result += ","
		}
		result += fmt.Sprintf("%q", value)
	}
	return result + "}", nil
}

func (a *StringArray) Scan(src any) error {
	if src == nil {
		*a = StringArray{}
		return nil
	}
	switch value := src.(type) {
	case []byte:
		return a.parseArray(string(value))
	case string:
		return a.parseArray(value)
	default:
		return fmt.Errorf("unsupported type for StringArray: %T", src)
	}
}

func (a *StringArray) parseArray(value string) error {
	if value == "{}" || value == "" {
		*a = StringArray{}
		return nil
	}
	value = value[1 : len(value)-1]
	var items []string
	current := ""
	inQuote := false
	for index := 0; index < len(value); index++ {
		character := value[index]
		if character == '"' {
			inQuote = !inQuote
		} else if character == ',' && !inQuote {
			items = append(items, current)
			current = ""
		} else {
			current += string(character)
		}
	}
	if current != "" {
		items = append(items, current)
	}
	*a = items
	return nil
}
