package agent

import (
	"strings"
	"testing"
)

func TestSkillsSummarySupportsMethodologyOnlySkills(t *testing.T) {
	loader := &SkillsLoader{}
	summary := loader.BuildSkillsSummary([]Skill{
		{
			Name:    "research-method",
			Layer:   "user",
			Content: "Use this evidence-grading workflow without running a script.",
		},
	})

	if strings.Contains(summary, "run its main script") {
		t.Fatal("skills summary must not assume every skill has an executable entrypoint")
	}
	if !strings.Contains(summary, "reasoning workflows with no executable entrypoint") {
		t.Fatal("skills summary must explain methodology-only skills")
	}
	if !strings.Contains(summary, "Follow the selected SKILL.md exactly") {
		t.Fatal("skills summary must defer invocation details to the selected skill")
	}
}
