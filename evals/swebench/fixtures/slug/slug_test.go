package slug

import "testing"

func TestSlugify(t *testing.T) {
	tests := map[string]string{
		"Hello World":           "hello-world",
		"  Multiple   Spaces  ": "multiple-spaces",
		"API: Fast & Safe":      "api-fast-safe",
		"already--slugged":      "already-slugged",
		"***":                   "",
	}
	for input, expected := range tests {
		if actual := Slugify(input); actual != expected {
			t.Errorf("Slugify(%q) = %q, want %q", input, actual, expected)
		}
	}
}
