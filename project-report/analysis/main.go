package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	evalpkg "github.com/fastclaw-ai/fastclaw/internal/eval"
)

const maxAssertionTokenGap = 8

var modes = []string{
	evalpkg.MultiAgentBaselineSoloOpenBook,
	evalpkg.MultiAgentBaselineSoloTwoPass,
	evalpkg.MultiAgentBaselineTeam,
	evalpkg.MultiAgentBaselineOracleTeam,
}

type matcherOptions struct {
	Name                string `json:"name"`
	NegationScope       bool   `json:"negation_scope"`
	HedgeScope          bool   `json:"hedge_scope"`
	ConditionalScope    bool   `json:"conditional_scope"`
	BoundedClauseGap    bool   `json:"bounded_clause_gap"`
	PluralMorphology    bool   `json:"plural_morphology"`
	ExtendedInflections bool   `json:"extended_inflections"`
}

type modeSummary struct {
	Passed int     `json:"passed"`
	Total  int     `json:"total"`
	Rate   float64 `json:"rate"`
	Low95  float64 `json:"wilson_low_95"`
	High95 float64 `json:"wilson_high_95"`
}

type pairedSummary struct {
	Left          string  `json:"left"`
	Right         string  `json:"right"`
	LeftOnly      int     `json:"left_only"`
	RightOnly     int     `json:"right_only"`
	Discordant    int     `json:"discordant"`
	DifferencePP  float64 `json:"difference_pp"`
	ExactTwoSided float64 `json:"exact_two_sided_p"`
}

type runSummary struct {
	Artifact          string `json:"artifact"`
	StoredDifferences int    `json:"stored_outcome_cells_changed_by_current_grader"`
}

type caseSummary struct {
	CaseID string         `json:"case_id"`
	Modes  map[string]int `json:"passes_by_mode"`
	Total  int            `json:"runs"`
}

type ablationSummary struct {
	Options matcherOptions         `json:"options"`
	Modes   map[string]modeSummary `json:"modes"`
}

type analysisOutput struct {
	Version             int                          `json:"version"`
	Suite               string                       `json:"suite"`
	SuiteSHA256         string                       `json:"suite_sha256"`
	Artifacts           []string                     `json:"artifacts"`
	CurrentGrader       map[string]modeSummary       `json:"current_grader_pooled_r2_r5"`
	PairedComparisons   []pairedSummary              `json:"paired_comparisons_r2_r5"`
	Cases               []caseSummary                `json:"case_matrix_r2_r5"`
	RegradeDrift        []runSummary                 `json:"regrade_drift_r1_r5"`
	Ablations           []ablationSummary            `json:"grader_ablation_r1_r5"`
	InterpretationNotes []string                     `json:"interpretation_notes"`
	Outcomes            map[string]map[string][]bool `json:"-"`
}

func main() {
	root, err := findRoot()
	check(err)
	suitePath := filepath.Join(root, "evals", "multiagent-finance-runtime.yaml")
	suite, err := evalpkg.LoadMultiAgentSuite(suitePath)
	check(err)

	allArtifacts := artifactPaths(root, 1, 5)
	pooledArtifacts := artifactPaths(root, 2, 5)
	current := currentOptions()
	pooledOutcomes, err := regradeArtifacts(suite, pooledArtifacts, current)
	check(err)
	allOutcomes, err := regradeArtifacts(suite, allArtifacts, current)
	check(err)

	result := analysisOutput{
		Version:       1,
		Suite:         suite.Name,
		SuiteSHA256:   suite.SourceSHA256,
		Artifacts:     baseNames(allArtifacts),
		CurrentGrader: summarizeModes(pooledOutcomes),
		PairedComparisons: []pairedSummary{
			paired(pooledOutcomes, evalpkg.MultiAgentBaselineTeam, evalpkg.MultiAgentBaselineSoloOpenBook),
			paired(pooledOutcomes, evalpkg.MultiAgentBaselineTeam, evalpkg.MultiAgentBaselineSoloTwoPass),
			paired(pooledOutcomes, evalpkg.MultiAgentBaselineTeam, evalpkg.MultiAgentBaselineOracleTeam),
		},
		Cases:        summarizeCases(pooledOutcomes),
		RegradeDrift: calculateDrift(suite, allArtifacts, current),
		Ablations:    calculateAblations(suite, allArtifacts),
		InterpretationNotes: []string{
			"The r2-r5 pooling is post hoc sensitivity analysis, not independent validation.",
			"All outputs are regraded without model calls; each artifact contributes six paired cases per mode.",
			"A zero difference at n=6 is an undetected effect, not evidence of equivalence.",
			"The extended-inflections switch is intentionally lightweight and demonstrates measurement sensitivity rather than a universally correct linguistic normalizer.",
		},
		Outcomes: allOutcomes,
	}

	encoded, err := json.MarshalIndent(result, "", "  ")
	check(err)
	encoded = append(encoded, '\n')
	outputPath := filepath.Join(root, "project-report", "finance_reanalysis.json")
	check(os.WriteFile(outputPath, encoded, 0o644))
	fmt.Println(outputPath)
}

func findRoot() (string, error) {
	directory, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		if _, err := os.Stat(filepath.Join(directory, "go.mod")); err == nil {
			return directory, nil
		}
		parent := filepath.Dir(directory)
		if parent == directory {
			return "", fmt.Errorf("repository root not found")
		}
		directory = parent
	}
}

func artifactPaths(root string, first, last int) []string {
	paths := make([]string, 0, last-first+1)
	for run := first; run <= last; run++ {
		paths = append(paths, filepath.Join(root, fmt.Sprintf("finance-runtime-formal-r%d.json", run)))
	}
	return paths
}

func baseNames(paths []string) []string {
	result := make([]string, len(paths))
	for index, path := range paths {
		result[index] = filepath.Base(path)
	}
	return result
}

func loadReport(path string) evalpkg.Report {
	data, err := os.ReadFile(path)
	check(err)
	var report evalpkg.Report
	check(json.Unmarshal(data, &report))
	return report
}

func currentOptions() matcherOptions {
	return matcherOptions{
		Name:             "current",
		NegationScope:    true,
		HedgeScope:       true,
		ConditionalScope: true,
		BoundedClauseGap: true,
		PluralMorphology: true,
	}
}

func calculateAblations(suite evalpkg.MultiAgentSuite, paths []string) []ablationSummary {
	options := []matcherOptions{currentOptions()}
	for _, change := range []func(*matcherOptions){
		func(option *matcherOptions) { option.Name = "without_negation_scope"; option.NegationScope = false },
		func(option *matcherOptions) { option.Name = "without_hedge_scope"; option.HedgeScope = false },
		func(option *matcherOptions) {
			option.Name = "without_conditional_scope"
			option.ConditionalScope = false
		},
		func(option *matcherOptions) {
			option.Name = "without_bounded_clause_gap"
			option.BoundedClauseGap = false
		},
		func(option *matcherOptions) {
			option.Name = "without_plural_morphology"
			option.PluralMorphology = false
		},
		func(option *matcherOptions) {
			option.Name = "with_extended_inflections"
			option.ExtendedInflections = true
		},
	} {
		option := currentOptions()
		change(&option)
		options = append(options, option)
	}

	result := make([]ablationSummary, 0, len(options))
	for _, option := range options {
		outcomes, err := regradeArtifacts(suite, paths, option)
		check(err)
		result = append(result, ablationSummary{Options: option, Modes: summarizeModes(outcomes)})
	}
	return result
}

func calculateDrift(suite evalpkg.MultiAgentSuite, paths []string, options matcherOptions) []runSummary {
	result := make([]runSummary, 0, len(paths))
	for _, path := range paths {
		report := loadReport(path)
		outcomes, err := regradeReport(suite, report, options)
		check(err)
		differences := 0
		for _, caseResult := range report.Cases {
			attempt := caseResult.Attempts[0]
			stored := map[string]bool{evalpkg.MultiAgentBaselineTeam: attempt.Passed}
			for _, baseline := range attempt.Baselines {
				stored[baseline.Mode] = baseline.Passed
			}
			for _, mode := range modes {
				if stored[mode] != outcomes[caseResult.ID][mode][0] {
					differences++
				}
			}
		}
		result = append(result, runSummary{Artifact: filepath.Base(path), StoredDifferences: differences})
	}
	return result
}

func regradeArtifacts(suite evalpkg.MultiAgentSuite, paths []string, options matcherOptions) (map[string]map[string][]bool, error) {
	combined := make(map[string]map[string][]bool)
	for _, path := range paths {
		report := loadReport(path)
		outcomes, err := regradeReport(suite, report, options)
		if err != nil {
			return nil, fmt.Errorf("%s: %w", filepath.Base(path), err)
		}
		for caseID, caseModes := range outcomes {
			if combined[caseID] == nil {
				combined[caseID] = make(map[string][]bool)
			}
			for mode, values := range caseModes {
				combined[caseID][mode] = append(combined[caseID][mode], values...)
			}
		}
	}
	return combined, nil
}

func regradeReport(suite evalpkg.MultiAgentSuite, report evalpkg.Report, options matcherOptions) (map[string]map[string][]bool, error) {
	cases := make(map[string]evalpkg.MultiAgentCase, len(suite.Cases))
	for _, evalCase := range suite.Cases {
		cases[evalCase.ID] = evalCase
	}
	result := make(map[string]map[string][]bool, len(report.Cases))
	for _, caseResult := range report.Cases {
		evalCase, exists := cases[caseResult.ID]
		if !exists {
			return nil, fmt.Errorf("case %q is absent from suite", caseResult.ID)
		}
		result[caseResult.ID] = make(map[string][]bool)
		for _, attempt := range caseResult.Attempts {
			result[caseResult.ID][evalpkg.MultiAgentBaselineTeam] = append(
				result[caseResult.ID][evalpkg.MultiAgentBaselineTeam],
				teamPass(evalCase, attempt.Output, attempt.Trace, options),
			)
			for _, baseline := range attempt.Baselines {
				if baseline.Mode == evalpkg.MultiAgentBaselineTeam {
					continue
				}
				if baseline.Error != "" {
					continue
				}
				result[caseResult.ID][baseline.Mode] = append(
					result[caseResult.ID][baseline.Mode],
					outcomePass(evalCase, baseline.Output, options),
				)
			}
		}
	}
	return result, nil
}

func outcomePass(evalCase evalpkg.MultiAgentCase, output string, options matcherOptions) bool {
	for _, milestone := range evalCase.Milestones {
		if !containsAllAssertions(output, milestone.Values, options) {
			return false
		}
	}
	return groundingViolations(output, evalCase.ForbiddenOutputValues, options) == 0
}

func teamPass(evalCase evalpkg.MultiAgentCase, output string, trace []evalpkg.TraceEvent, options matcherOptions) bool {
	if !outcomePass(evalCase, output, options) {
		return false
	}
	expected := make(map[string]evalpkg.MultiAgentCollaborator, len(evalCase.Agents))
	for _, collaborator := range evalCase.Agents {
		expected[collaborator.ID] = collaborator
	}
	valid := make(map[string]bool, len(expected))
	unique := make(map[string]struct{})
	total := 0
	for _, event := range trace {
		if event.Type != "tool_call" || event.Name != "spawn_subagent" {
			continue
		}
		total++
		var arguments struct {
			AgentID string `json:"agentId"`
			Task    string `json:"task"`
		}
		if json.Unmarshal([]byte(event.Arguments), &arguments) != nil {
			continue
		}
		if arguments.AgentID != "" {
			unique[arguments.AgentID] = struct{}{}
		}
		collaborator, exists := expected[arguments.AgentID]
		if exists && containsAllFold(arguments.Task, collaborator.TaskValues, options) {
			valid[arguments.AgentID] = true
		}
	}
	if len(valid) != len(expected) || len(unique) != len(expected) {
		return false
	}
	for _, collaborator := range evalCase.Agents {
		if collaborator.Fault == nil && (!valid[collaborator.ID] || !containsAllAssertions(output, collaborator.ContributionValues, options)) {
			return false
		}
	}
	maximum := evalCase.MaxDelegations
	if maximum == 0 {
		maximum = len(evalCase.Agents)
	}
	return total <= maximum
}

func summarizeModes(outcomes map[string]map[string][]bool) map[string]modeSummary {
	result := make(map[string]modeSummary, len(modes))
	for _, mode := range modes {
		passed, total := 0, 0
		for _, caseModes := range outcomes {
			for _, value := range caseModes[mode] {
				total++
				if value {
					passed++
				}
			}
		}
		low, high := wilson(passed, total)
		result[mode] = modeSummary{Passed: passed, Total: total, Rate: ratio(passed, total), Low95: low, High95: high}
	}
	return result
}

func summarizeCases(outcomes map[string]map[string][]bool) []caseSummary {
	caseIDs := make([]string, 0, len(outcomes))
	for caseID := range outcomes {
		caseIDs = append(caseIDs, caseID)
	}
	sort.Strings(caseIDs)
	result := make([]caseSummary, 0, len(caseIDs))
	for _, caseID := range caseIDs {
		counts := make(map[string]int, len(modes))
		total := 0
		for _, mode := range modes {
			for _, passed := range outcomes[caseID][mode] {
				if passed {
					counts[mode]++
				}
			}
			if len(outcomes[caseID][mode]) > total {
				total = len(outcomes[caseID][mode])
			}
		}
		result = append(result, caseSummary{CaseID: caseID, Modes: counts, Total: total})
	}
	return result
}

func paired(outcomes map[string]map[string][]bool, left, right string) pairedSummary {
	leftOnly, rightOnly, total, leftPassed, rightPassed := 0, 0, 0, 0, 0
	for _, caseModes := range outcomes {
		leftValues, rightValues := caseModes[left], caseModes[right]
		limit := min(len(leftValues), len(rightValues))
		for index := 0; index < limit; index++ {
			total++
			if leftValues[index] {
				leftPassed++
			}
			if rightValues[index] {
				rightPassed++
			}
			if leftValues[index] && !rightValues[index] {
				leftOnly++
			} else if !leftValues[index] && rightValues[index] {
				rightOnly++
			}
		}
	}
	return pairedSummary{
		Left:          left,
		Right:         right,
		LeftOnly:      leftOnly,
		RightOnly:     rightOnly,
		Discordant:    leftOnly + rightOnly,
		DifferencePP:  100 * ratio(leftPassed-rightPassed, total),
		ExactTwoSided: exactBinomialTwoSided(leftOnly, rightOnly),
	}
}

func wilson(successes, total int) (float64, float64) {
	if total == 0 {
		return 0, 0
	}
	z := 1.959963984540054
	n := float64(total)
	p := float64(successes) / n
	denominator := 1 + z*z/n
	center := (p + z*z/(2*n)) / denominator
	spread := z * math.Sqrt(p*(1-p)/n+z*z/(4*n*n)) / denominator
	return center - spread, center + spread
}

func exactBinomialTwoSided(leftOnly, rightOnly int) float64 {
	discordant := leftOnly + rightOnly
	if discordant == 0 {
		return math.NaN()
	}
	extreme := min(leftOnly, rightOnly)
	probability := 0.0
	for value := 0; value <= extreme; value++ {
		probability += combination(discordant, value) / math.Pow(2, float64(discordant))
	}
	return min(1.0, 2*probability)
}

func combination(n, k int) float64 {
	if k > n-k {
		k = n - k
	}
	result := 1.0
	for value := 1; value <= k; value++ {
		result *= float64(n-k+value) / float64(value)
	}
	return result
}

func ratio(numerator, denominator int) float64 {
	if denominator == 0 {
		return 0
	}
	return float64(numerator) / float64(denominator)
}

func containsAllFold(text string, values []string, options matcherOptions) bool {
	normalizedText := normalizeText(text, options)
	for _, value := range values {
		matched := false
		for _, alternative := range strings.Split(value, "||") {
			if strings.Contains(normalizedText, normalizeText(alternative, options)) {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}
	return true
}

func containsAllAssertions(text string, values []string, options matcherOptions) bool {
	for _, value := range values {
		if !containsRequiredAssertion(text, value, options) {
			return false
		}
	}
	return true
}

func containsRequiredAssertion(text, value string, options matcherOptions) bool {
	for _, alternative := range strings.Split(value, "||") {
		expected := strings.Fields(normalizeText(alternative, options))
		if len(expected) == 0 {
			continue
		}
		for _, clause := range matchClauses(text) {
			actual := strings.Fields(normalizeText(clause, options))
			for searchFrom := 0; searchFrom < len(actual); {
				gap := maxAssertionTokenGap
				if !options.BoundedClauseGap {
					gap = len(actual)
				}
				start, end, ok := wordsAppearInOrder(actual, expected, searchFrom, gap, options)
				if !ok {
					break
				}
				if expectedContainsNegation(expected, options) {
					if !options.ConditionalScope || !hasConditionalScope(actual, start, options) {
						return true
					}
				} else if !hasNegationScope(actual, start, end, 0, options) {
					return true
				}
				searchFrom = start + 1
			}
		}
	}
	return false
}

func containsForbiddenAssertion(text, value string, options matcherOptions) bool {
	for _, alternative := range strings.Split(value, "||") {
		expected := strings.Fields(normalizeText(alternative, options))
		if len(expected) == 0 {
			continue
		}
		for _, clause := range matchClauses(text) {
			actual := strings.Fields(normalizeText(clause, options))
			for start := 0; start+len(expected) <= len(actual); start++ {
				if !equalWords(actual[start:start+len(expected)], expected, options) {
					continue
				}
				if expectedContainsNegation(expected, options) {
					if !options.ConditionalScope || !hasConditionalScope(actual, start, options) {
						return true
					}
				} else if !hasNegationScope(actual, start, start+len(expected), 5, options) {
					return true
				}
			}
		}
	}
	return false
}

func groundingViolations(output string, forbidden []string, options matcherOptions) int {
	violations := 0
	for _, value := range forbidden {
		if containsForbiddenAssertion(output, value, options) {
			violations++
		}
	}
	return violations
}

func matchClauses(text string) []string {
	text = strings.ToLower(text)
	text = strings.NewReplacer(
		";", "\n", "。", "\n", "；", "\n", "!", "\n", "！", "\n", "?", "\n", "？", "\n",
		" but ", ".", " and ", "\n", " however ", "\n", " yet ", "\n",
	).Replace(text)
	var clauses []string
	var clause strings.Builder
	for index := 0; index < len(text); index++ {
		character := text[index]
		if character == '.' && !(index > 0 && index+1 < len(text) && isDigit(text[index-1]) && isDigit(text[index+1])) {
			clauses = append(clauses, clause.String())
			clause.Reset()
			continue
		}
		if character == '\n' {
			clauses = append(clauses, clause.String())
			clause.Reset()
			continue
		}
		clause.WriteByte(character)
	}
	return append(clauses, clause.String())
}

func isDigit(value byte) bool {
	return value >= '0' && value <= '9'
}

func wordsAppearInOrder(actual, expected []string, searchFrom, maxGap int, options matcherOptions) (int, int, bool) {
	for start := max(0, searchFrom); start < len(actual); start++ {
		if !equalWord(actual[start], expected[0], options) {
			continue
		}
		actualIndex := start
		matched := true
		for expectedIndex := 1; expectedIndex < len(expected); expectedIndex++ {
			found := false
			limit := min(len(actual), actualIndex+maxGap+2)
			for candidate := actualIndex + 1; candidate < limit; candidate++ {
				if equalWord(actual[candidate], expected[expectedIndex], options) {
					actualIndex = candidate
					found = true
					break
				}
			}
			if !found {
				matched = false
				break
			}
		}
		if matched {
			return start, actualIndex + 1, true
		}
	}
	return 0, 0, false
}

func equalWords(actual, expected []string, options matcherOptions) bool {
	if len(actual) != len(expected) {
		return false
	}
	for index := range expected {
		if !equalWord(actual[index], expected[index], options) {
			return false
		}
	}
	return true
}

func equalWord(left, right string, options matcherOptions) bool {
	return normalizeWord(left, options) == normalizeWord(right, options)
}

func hasNegationScope(words []string, start, end, trailingWindow int, options matcherOptions) bool {
	windowStart := max(0, start-5)
	windowEnd := min(len(words), end+trailingWindow)
	if options.NegationScope {
		negations := map[string]struct{}{
			"no": {}, "not": {}, "cannot": {}, "can't": {}, "without": {}, "unknown": {}, "unconfirmed": {},
			"unverified": {}, "unavailable": {}, "uncertain": {}, "insufficient": {}, "absent": {}, "lack": {},
			"lacks": {}, "none": {}, "excluded": {}, "exclude": {}, "never": {}, "refuse": {}, "refused": {},
			"reject": {}, "rejected": {}, "deny": {}, "denied": {},
		}
		for index := windowStart; index < windowEnd; index++ {
			word := normalizeWord(words[index], options)
			if word == "not" && index+1 < len(words) && normalizeWord(words[index+1], options) == "only" {
				continue
			}
			if _, exists := negations[word]; exists {
				return true
			}
		}
	}
	if options.HedgeScope {
		hedges := map[string]struct{}{"may": {}, "might": {}, "could": {}, "possible": {}, "possibly": {}}
		for index := windowStart; index < start; index++ {
			if _, exists := hedges[normalizeWord(words[index], options)]; exists {
				return true
			}
		}
	}
	return false
}

func hasConditionalScope(words []string, start int, options matcherOptions) bool {
	for index := max(0, start-5); index < start; index++ {
		switch normalizeWord(words[index], options) {
		case "if", "unless", "whether":
			return true
		}
	}
	return false
}

func expectedContainsNegation(words []string, options matcherOptions) bool {
	for _, word := range words {
		switch normalizeWord(word, options) {
		case "no", "not", "cannot", "can't", "without", "never", "none", "unknown", "unconfirmed", "unverified",
			"unavailable", "uncertain", "insufficient", "absent", "lack", "lacks", "excluded", "exclude", "refuse",
			"refused", "reject", "rejected", "deny", "denied":
			return true
		}
	}
	return false
}

func normalizeText(value string, options matcherOptions) string {
	value = strings.ToLower(value)
	value = strings.ReplaceAll(value, "instead of", "not")
	value = strings.ReplaceAll(value, "rather than", "not")
	value = strings.ReplaceAll(value, "%", " percent ")
	value = strings.NewReplacer(
		",", "", "`", "", "*", "", "-", " ", "‑", " ", "–", " ", "—", " ", "_", " ", "/", " ",
		":", " ", "=", " ", ">", " above ", "<", " below ", "¥", " ", "￥", " ", "→", " to ",
		"“", " ", "”", " ", "‘", " ", "’", " ", "\"", " ", "'", " ", "|", " ", "(", " ", ")", " ",
	).Replace(value)
	numberWords := map[string]string{
		"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
		"six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
	}
	stopWords := map[string]struct{}{"a": {}, "an": {}, "are": {}, "is": {}, "of": {}, "the": {}, "was": {}, "were": {}}
	fields := strings.Fields(value)
	normalized := make([]string, 0, len(fields))
	for _, field := range fields {
		if _, skip := stopWords[field]; skip {
			continue
		}
		if number, exists := numberWords[field]; exists {
			field = number
		}
		normalized = append(normalized, normalizeWord(field, options))
	}
	return strings.Join(normalized, " ")
}

func normalizeWord(value string, options matcherOptions) string {
	value = strings.Trim(strings.ToLower(value), `."'“”‘’[]{}|,;!?`)
	if options.PluralMorphology {
		if len(value) > 4 && strings.HasSuffix(value, "sses") {
			value = strings.TrimSuffix(value, "es")
		} else if len(value) > 4 && strings.HasSuffix(value, "ies") {
			value = strings.TrimSuffix(value, "ies") + "y"
		} else if len(value) > 3 && strings.HasSuffix(value, "s") &&
			!strings.HasSuffix(value, "ss") && !strings.HasSuffix(value, "is") && !strings.HasSuffix(value, "us") {
			value = strings.TrimSuffix(value, "s")
		}
	}
	if options.ExtendedInflections {
		for _, suffix := range []string{"ing", "ed", "ion"} {
			if len(value) > len(suffix)+3 && strings.HasSuffix(value, suffix) {
				value = strings.TrimSuffix(value, suffix)
				break
			}
		}
		if len(value) > 5 && strings.HasSuffix(value, "e") {
			value = strings.TrimSuffix(value, "e")
		}
	}
	return value
}

func check(err error) {
	if err != nil {
		panic(err)
	}
}
