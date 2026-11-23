package backoff

import "time"

func Delay(base, maximum time.Duration, attempt int) time.Duration {
	if attempt < 0 {
		attempt = 0
	}
	delay := base << (attempt + 1)
	if delay > maximum {
		return maximum
	}
	return delay
}
