package pagination

import "testing"

func TestPageBounds(t *testing.T) {
	tests := []struct {
		total, page, pageSize int
		start, end            int
	}{
		{total: 25, page: 1, pageSize: 10, start: 0, end: 10},
		{total: 25, page: 2, pageSize: 10, start: 10, end: 20},
		{total: 25, page: 3, pageSize: 10, start: 20, end: 25},
		{total: 25, page: 4, pageSize: 10, start: 25, end: 25},
		{total: 25, page: 0, pageSize: 10, start: 0, end: 0},
		{total: 25, page: 1, pageSize: 0, start: 0, end: 0},
	}
	for _, test := range tests {
		start, end := PageBounds(test.total, test.page, test.pageSize)
		if start != test.start || end != test.end {
			t.Errorf(
				"PageBounds(%d, %d, %d) = (%d, %d), want (%d, %d)",
				test.total,
				test.page,
				test.pageSize,
				start,
				end,
				test.start,
				test.end,
			)
		}
	}
}
