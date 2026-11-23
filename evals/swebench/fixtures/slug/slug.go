package slug

import "strings"

func Slugify(input string) string {
	return strings.ReplaceAll(strings.ToLower(strings.TrimSpace(input)), " ", "-")
}
