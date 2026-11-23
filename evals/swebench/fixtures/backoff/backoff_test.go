package backoff

import (
	"testing"
	"time"
)

func TestDelay(t *testing.T) {
	base := 100 * time.Millisecond
	maximum := time.Second
	tests := []struct {
		attempt  int
		expected time.Duration
	}{
		{attempt: -1, expected: 100 * time.Millisecond},
		{attempt: 0, expected: 100 * time.Millisecond},
		{attempt: 1, expected: 200 * time.Millisecond},
		{attempt: 2, expected: 400 * time.Millisecond},
		{attempt: 4, expected: time.Second},
	}
	for _, test := range tests {
		if actual := Delay(base, maximum, test.attempt); actual != test.expected {
			t.Errorf("Delay(%v, %v, %d) = %v, want %v", base, maximum, test.attempt, actual, test.expected)
		}
	}
}
