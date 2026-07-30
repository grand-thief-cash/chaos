package controller

import (
	"reflect"
	"testing"
)

func TestStripVirtualBarFields(t *testing.T) {
	tests := []struct {
		name   string
		input  []string
		output []string
	}{
		{name: "empty", input: nil, output: nil},
		{
			name:   "security id removed",
			input:  []string{"security_id", "trade_date", "open", "close"},
			output: []string{"trade_date", "open", "close"},
		},
		{name: "only virtual field", input: []string{"security_id"}, output: []string{}},
		{name: "physical fields unchanged", input: []string{"symbol", "volume"}, output: []string{"symbol", "volume"}},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := stripVirtualBarFields(test.input); !reflect.DeepEqual(got, test.output) {
				t.Fatalf("stripVirtualBarFields(%v) = %v, want %v", test.input, got, test.output)
			}
		})
	}
}
