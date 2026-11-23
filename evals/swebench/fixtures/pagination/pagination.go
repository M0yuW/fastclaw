package pagination

func PageBounds(total, page, pageSize int) (start, end int) {
	if total <= 0 || pageSize <= 0 {
		return 0, 0
	}
	start = page * pageSize
	if start >= total {
		return total, total
	}
	end = start + pageSize
	if end > total {
		end = total
	}
	return start, end
}
