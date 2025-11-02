package model

import "testing"

func TestNormalizeCron(t *testing.T) {
	cases := []struct{ in, want string }{
		{"* * * * *", "0 * * * * *"},
		{"0 * * * * *", "0 * * * * *"},
		{"5 1 2 3 4 5", "5 1 2 3 4 5"},
	}
	for _, c := range cases {
		got := NormalizeCron(c.in)
		if got != c.want {
			t.Fatalf("normalize %q => %q want %q", c.in, got, c.want)
		}
	}
}
