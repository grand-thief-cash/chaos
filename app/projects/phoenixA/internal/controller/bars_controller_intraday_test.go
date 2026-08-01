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
			name:   "display symbol removed",
			input:  []string{"symbol", "security_id", "trade_date", "close"},
			output: []string{"security_id", "trade_date", "close"},
		},
		{name: "only virtual field", input: []string{"symbol"}, output: []string{}},
		{name: "physical fields unchanged", input: []string{"security_id", "volume"}, output: []string{"security_id", "volume"}},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := stripVirtualBarFields(test.input); !reflect.DeepEqual(got, test.output) {
				t.Fatalf("stripVirtualBarFields(%v) = %v, want %v", test.input, got, test.output)
			}
		})
	}
}
