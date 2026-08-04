package eval

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

const maxSWETestOutputBytes = 64 << 10
const maxSWEEditableFileBytes = 1 << 20

type SWESuite struct {
	Version     int       `json:"version" yaml:"version"`
	Name        string    `json:"name" yaml:"name"`
	Description string    `json:"description,omitempty" yaml:"description,omitempty"`
	Defaults    Defaults  `json:"defaults,omitempty" yaml:"defaults,omitempty"`
	Cases       []SWECase `json:"cases" yaml:"cases"`
	Source      string    `json:"-" yaml:"-"`
}

type SWECase struct {
	InstanceID        string   `json:"instance_id" yaml:"instance_id"`
	Repository        string   `json:"repository,omitempty" yaml:"repository,omitempty"`
	BaseCommit        string   `json:"base_commit,omitempty" yaml:"base_commit,omitempty"`
	ProblemStatement  string   `json:"problem_statement" yaml:"problem_statement"`
	Fixture           string   `json:"fixture" yaml:"fixture"`
	EditableFiles     []string `json:"editable_files" yaml:"editable_files"`
	TestCommand       string   `json:"test_command" yaml:"test_command"`
	SkipBaselineCheck bool     `json:"skip_baseline_check,omitempty" yaml:"skip_baseline_check,omitempty"`
	AgentID           string   `json:"agent_id,omitempty" yaml:"agent_id,omitempty"`
	Model             string   `json:"model,omitempty" yaml:"model,omitempty"`
	Repetitions       int      `json:"repetitions,omitempty" yaml:"repetitions,omitempty"`
	Timeout           Duration `json:"timeout,omitempty" yaml:"timeout,omitempty"`
	Tags              []string `json:"tags,omitempty" yaml:"tags,omitempty"`
}

type SWERunner struct {
	Executor Executor
	Options  RunOptions
}

type SWEPrediction struct {
	InstanceID      string `json:"instance_id"`
	ModelNameOrPath string `json:"model_name_or_path"`
	ModelPatch      string `json:"model_patch"`
}

func LoadSWESuite(path string) (SWESuite, error) {
	file, err := os.Open(path)
	if err != nil {
		return SWESuite{}, fmt.Errorf("open SWE eval suite: %w", err)
	}
	defer file.Close()

	var suite SWESuite
	decoder := yaml.NewDecoder(file)
	decoder.KnownFields(true)
	if err := decoder.Decode(&suite); err != nil {
		return SWESuite{}, fmt.Errorf("decode SWE eval suite: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return SWESuite{}, errors.New("decode SWE eval suite: multiple YAML documents are not supported")
		}
		return SWESuite{}, fmt.Errorf("decode SWE eval suite: %w", err)
	}
	suite.Source = path
	if err := suite.Validate(); err != nil {
		return SWESuite{}, err
	}
	return suite, nil
}

func (s *SWESuite) Validate() error {
	if s.Version != SuiteVersion {
		return fmt.Errorf("SWE eval suite version must be %d", SuiteVersion)
	}
	if strings.TrimSpace(s.Name) == "" {
		return errors.New("SWE eval suite name is required")
	}
	if len(s.Cases) == 0 {
		return errors.New("SWE eval suite must contain at least one case")
	}
	if s.Defaults.Repetitions < 0 {
		return errors.New("default repetitions cannot be negative")
	}
	if s.Defaults.Timeout.Value() < 0 {
		return errors.New("default timeout cannot be negative")
	}

	seen := make(map[string]struct{}, len(s.Cases))
	for caseIndex := range s.Cases {
		evalCase := &s.Cases[caseIndex]
		if strings.TrimSpace(evalCase.InstanceID) == "" {
			return fmt.Errorf("case %d: instance_id is required", caseIndex+1)
		}
		if _, exists := seen[evalCase.InstanceID]; exists {
			return fmt.Errorf("case %q: duplicate instance_id", evalCase.InstanceID)
		}
		seen[evalCase.InstanceID] = struct{}{}
		if strings.TrimSpace(evalCase.ProblemStatement) == "" {
			return fmt.Errorf("case %q: problem_statement is required", evalCase.InstanceID)
		}
		if strings.TrimSpace(evalCase.Fixture) == "" {
			return fmt.Errorf("case %q: fixture is required", evalCase.InstanceID)
		}
		if len(evalCase.EditableFiles) == 0 {
			return fmt.Errorf("case %q: editable_files is required", evalCase.InstanceID)
		}
		fileSet := make(map[string]struct{}, len(evalCase.EditableFiles))
		for fileIndex, path := range evalCase.EditableFiles {
			cleaned, err := validateRelativeRepoPath(path)
			if err != nil {
				return fmt.Errorf("case %q editable file %d: %w", evalCase.InstanceID, fileIndex+1, err)
			}
			if _, exists := fileSet[cleaned]; exists {
				return fmt.Errorf("case %q: duplicate editable file %q", evalCase.InstanceID, cleaned)
			}
			fileSet[cleaned] = struct{}{}
			evalCase.EditableFiles[fileIndex] = cleaned
		}
		if strings.TrimSpace(evalCase.TestCommand) == "" {
			return fmt.Errorf("case %q: test_command is required", evalCase.InstanceID)
		}
		if evalCase.Repetitions < 0 {
			return fmt.Errorf("case %q: repetitions cannot be negative", evalCase.InstanceID)
		}
		if evalCase.Timeout.Value() < 0 {
			return fmt.Errorf("case %q: timeout cannot be negative", evalCase.InstanceID)
		}
	}
	return nil
}

func (r SWERunner) Run(ctx context.Context, suite SWESuite) (Report, error) {
	if r.Executor == nil {
		return Report{}, fmt.Errorf("eval executor is required")
	}
	if err := suite.Validate(); err != nil {
		return Report{}, err
	}

	fixtures := make(map[string]string, len(suite.Cases))
	for _, evalCase := range suite.Cases {
		fixture, err := resolveSWEFixture(suite.Source, evalCase.Fixture)
		if err != nil {
			return Report{}, fmt.Errorf("case %q: %w", evalCase.InstanceID, err)
		}
		fixtures[evalCase.InstanceID] = fixture
		if !evalCase.SkipBaselineCheck {
			baselineContext, cancel := context.WithTimeout(
				ctx,
				sweTimeout(suite, evalCase, r.Options.Timeout),
			)
			err := verifySWEBaseline(baselineContext, fixture, evalCase.TestCommand)
			cancel()
			if err != nil {
				return Report{}, fmt.Errorf("case %q: %w", evalCase.InstanceID, err)
			}
		}
	}

	startedAt := time.Now()
	sessionPrefix := r.Options.SessionKeyPrefix
	if sessionPrefix == "" {
		sessionPrefix = "swe-eval"
	}
	runID := fmt.Sprintf(
		"%s-%d-%d",
		sanitizeSessionPart(sessionPrefix),
		startedAt.UnixNano(),
		runSequence.Add(1),
	)
	report := Report{
		Version:     SuiteVersion,
		Suite:       suite.Name,
		Description: suite.Description,
		Source:      suite.Source,
		StartedAt:   startedAt,
		Cases:       make([]CaseResult, 0, len(suite.Cases)),
	}

	for _, evalCase := range suite.Cases {
		caseResult := CaseResult{
			ID:          evalCase.InstanceID,
			Description: evalCase.ProblemStatement,
			Tags:        append([]string(nil), evalCase.Tags...),
		}
		repetitions := sweRepetitions(suite, evalCase, r.Options.Repetitions)
		for attempt := 1; attempt <= repetitions; attempt++ {
			caseResult.Attempts = append(
				caseResult.Attempts,
				r.runAttempt(ctx, suite, evalCase, fixtures[evalCase.InstanceID], attempt, runID),
			)
		}
		caseResult.PassAt1 = caseResult.Attempts[0].Passed
		caseResult.Consistent = attemptsConsistent(caseResult.Attempts)
		for _, attempt := range caseResult.Attempts {
			caseResult.PassAtK = caseResult.PassAtK || attempt.Passed
		}
		report.Cases = append(report.Cases, caseResult)
	}

	report.FinishedAt = time.Now()
	report.DurationMS = milliseconds(report.FinishedAt.Sub(startedAt))
	report.Metrics = calculateMetrics(report.Cases)
	return report, nil
}

func (r SWERunner) runAttempt(
	ctx context.Context,
	suite SWESuite,
	evalCase SWECase,
	fixture string,
	attempt int,
	runID string,
) AttemptResult {
	timeout := sweTimeout(suite, evalCase, r.Options.Timeout)
	attemptContext, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	startedAt := time.Now()

	files, err := loadEditableFiles(fixture, evalCase.EditableFiles)
	if err != nil {
		return sweErrorAttempt(attempt, startedAt, err)
	}
	agentID := firstNonEmpty(r.Options.AgentID, evalCase.AgentID, suite.Defaults.AgentID)
	model := firstNonEmpty(r.Options.Model, evalCase.Model, suite.Defaults.Model)
	sessionKey := fmt.Sprintf(
		"%s-%s-%s-%d",
		runID,
		sanitizeSessionPart(suite.Name),
		sanitizeSessionPart(evalCase.InstanceID),
		attempt,
	)
	response, err := r.Executor.Execute(attemptContext, ExecutionRequest{
		Prompt:     swePrompt(evalCase),
		AgentID:    agentID,
		Model:      model,
		SessionKey: sessionKey,
		Tools:      sweRepositoryTools(),
		State:      map[string]any{"files": stringMapToAny(files)},
	})
	if err != nil {
		result := sweErrorAttempt(attempt, startedAt, err)
		result.Model = model
		return result
	}

	result := AttemptResult{
		Attempt:   attempt,
		Kind:      "swe",
		Output:    response.Output,
		Model:     firstNonEmpty(response.Model, model),
		Usage:     response.Usage,
		Trace:     response.Trace,
		LatencyMS: milliseconds(time.Since(startedAt)),
	}
	updatedFiles, stateErr := extractEditableFiles(response.State, evalCase.EditableFiles)
	if stateErr != nil {
		result.Error = stateErr.Error()
		result.Graders = []GraderResult{
			{Type: "swe_patch", Passed: false, Message: stateErr.Error()},
			{Type: "swe_tests", Passed: false, Message: "tests were not executed"},
		}
		return result
	}

	workspace, err := prepareSWEWorkspace(fixture)
	if err != nil {
		result.Error = err.Error()
		return result
	}
	defer os.RemoveAll(workspace)
	if err := writeEditableFiles(workspace, updatedFiles); err != nil {
		result.Error = err.Error()
		return result
	}
	patch, err := gitDiff(workspace)
	if err != nil {
		result.Error = err.Error()
		return result
	}
	result.Patch = patch
	patchGenerated := strings.TrimSpace(patch) != ""

	testsExecuted, testsPassed, testOutput, testErr := runSWECommand(
		attemptContext,
		workspace,
		evalCase.TestCommand,
	)
	result.Completed = testsExecuted
	result.TestsPassed = testsPassed
	result.TestOutput = testOutput
	result.LatencyMS = milliseconds(time.Since(startedAt))
	result.Graders = []GraderResult{
		{Type: "swe_patch", Passed: patchGenerated},
		{Type: "swe_tests", Passed: testsPassed, Message: sweTestMessage(testsExecuted, testsPassed, testErr)},
	}
	result.Passed = patchGenerated && testsPassed
	if testErr != nil && !testsExecuted {
		result.Error = testErr.Error()
	}
	return result
}

func sweRepositoryTools() []ToolDefinition {
	pathParameter := map[string]any{
		"type": "object",
		"properties": map[string]any{
			"path": map[string]any{"type": "string"},
		},
		"required": []string{"path"},
	}
	return []ToolDefinition{
		{
			Name:        "list_files",
			Description: "List editable repository files. Hidden tests are intentionally unavailable.",
			Parameters:  map[string]any{"type": "object", "properties": map[string]any{}},
			Behavior:    &StateToolBehavior{ResultKeysPath: "files"},
		},
		{
			Name:        "read_file",
			Description: "Read an editable repository file.",
			Parameters:  pathParameter,
			Behavior: &StateToolBehavior{
				ResultMapPath:        "files",
				ResultMapKeyArgument: "path",
			},
		},
		{
			Name:        "write_file",
			Description: "Replace the complete content of an editable repository file.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"path":    map[string]any{"type": "string"},
					"content": map[string]any{"type": "string"},
				},
				"required": []string{"path", "content"},
			},
			Behavior: &StateToolBehavior{
				Updates: []StateUpdate{
					{
						MapPath:           "files",
						KeyFromArgument:   "path",
						ValueFromArgument: "content",
					},
				},
				Result: map[string]any{"ok": true},
			},
		},
	}
}

func swePrompt(evalCase SWECase) string {
	return fmt.Sprintf(
		`You are resolving a software repository issue.

Instance: %s
Repository: %s

Problem statement:
%s

Use list_files and read_file to inspect the editable source. Use write_file to
replace complete file contents with your fix. Hidden tests will run after you
finish. You do not have shell access, and you must not create new files.`,
		evalCase.InstanceID,
		firstNonEmpty(evalCase.Repository, "local fixture"),
		evalCase.ProblemStatement,
	)
}

func verifySWEBaseline(ctx context.Context, fixture, command string) error {
	workspace, err := copySWEFixture(fixture)
	if err != nil {
		return err
	}
	defer os.RemoveAll(workspace)
	executed, passed, output, runErr := runSWECommand(ctx, workspace, command)
	if !executed {
		return fmt.Errorf("baseline tests could not execute: %w", runErr)
	}
	if passed {
		return errors.New("baseline tests unexpectedly pass")
	}
	if strings.TrimSpace(output) == "" {
		return errors.New("baseline tests failed without output")
	}
	return nil
}

func resolveSWEFixture(source, fixture string) (string, error) {
	path := fixture
	if !filepath.IsAbs(path) && source != "" {
		path = filepath.Join(filepath.Dir(source), path)
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", fmt.Errorf("resolve fixture: %w", err)
	}
	info, err := os.Stat(absolute)
	if err != nil {
		return "", fmt.Errorf("stat fixture: %w", err)
	}
	if !info.IsDir() {
		return "", fmt.Errorf("fixture %q is not a directory", absolute)
	}
	return absolute, nil
}

func validateRelativeRepoPath(path string) (string, error) {
	if strings.TrimSpace(path) == "" {
		return "", errors.New("path is required")
	}
	if filepath.IsAbs(path) {
		return "", errors.New("path must be relative")
	}
	cleaned := filepath.Clean(path)
	if cleaned == "." || cleaned == ".." || strings.HasPrefix(cleaned, ".."+string(filepath.Separator)) {
		return "", errors.New("path must stay inside the repository")
	}
	return filepath.ToSlash(cleaned), nil
}

func loadEditableFiles(fixture string, paths []string) (map[string]string, error) {
	files := make(map[string]string, len(paths))
	for _, path := range paths {
		content, err := os.ReadFile(filepath.Join(fixture, filepath.FromSlash(path)))
		if err != nil {
			return nil, fmt.Errorf("read editable file %q: %w", path, err)
		}
		files[path] = string(content)
	}
	return files, nil
}

func extractEditableFiles(state map[string]any, editable []string) (map[string]string, error) {
	if state == nil {
		return nil, errors.New("agent response did not return repository state")
	}
	rawFiles, ok := state["files"].(map[string]any)
	if !ok {
		return nil, errors.New("agent repository state has no files object")
	}
	allowed := make(map[string]struct{}, len(editable))
	for _, path := range editable {
		allowed[path] = struct{}{}
	}
	if len(rawFiles) != len(allowed) {
		return nil, errors.New("agent added or removed repository files")
	}
	files := make(map[string]string, len(rawFiles))
	for path, rawContent := range rawFiles {
		if _, exists := allowed[path]; !exists {
			return nil, fmt.Errorf("agent modified undeclared file %q", path)
		}
		content, ok := rawContent.(string)
		if !ok {
			return nil, fmt.Errorf("agent produced non-text content for %q", path)
		}
		if len(content) > maxSWEEditableFileBytes {
			return nil, fmt.Errorf("agent produced oversized content for %q", path)
		}
		files[path] = content
	}
	return files, nil
}

func writeEditableFiles(workspace string, files map[string]string) error {
	for path, content := range files {
		fullPath := filepath.Join(workspace, filepath.FromSlash(path))
		info, err := os.Stat(fullPath)
		if err != nil {
			return fmt.Errorf("stat editable file %q: %w", path, err)
		}
		if err := os.WriteFile(fullPath, []byte(content), info.Mode().Perm()); err != nil {
			return fmt.Errorf("write editable file %q: %w", path, err)
		}
	}
	return nil
}

func stringMapToAny(values map[string]string) map[string]any {
	result := make(map[string]any, len(values))
	for key, value := range values {
		result[key] = value
	}
	return result
}

func prepareSWEWorkspace(fixture string) (string, error) {
	workspace, err := copySWEFixture(fixture)
	if err != nil {
		return "", err
	}
	if err := runGit(workspace, "init", "-q"); err != nil {
		os.RemoveAll(workspace)
		return "", err
	}
	if err := runGit(workspace, "add", "."); err != nil {
		os.RemoveAll(workspace)
		return "", err
	}
	if err := runGit(
		workspace,
		"-c", "user.name=FastClaw Eval",
		"-c", "user.email=eval@fastclaw.local",
		"commit", "-qm", "baseline",
	); err != nil {
		os.RemoveAll(workspace)
		return "", err
	}
	return workspace, nil
}

func copySWEFixture(fixture string) (string, error) {
	workspace, err := os.MkdirTemp("", "fastclaw-swe-*")
	if err != nil {
		return "", fmt.Errorf("create SWE workspace: %w", err)
	}
	err = filepath.WalkDir(fixture, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(fixture, path)
		if err != nil {
			return err
		}
		if relative == "." {
			return nil
		}
		if entry.Name() == ".git" && entry.IsDir() {
			return filepath.SkipDir
		}
		target := filepath.Join(workspace, relative)
		if entry.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("fixture symlinks are not supported: %s", relative)
		}
		if entry.IsDir() {
			return os.MkdirAll(target, 0o700)
		}
		if !entry.Type().IsRegular() {
			return fmt.Errorf("unsupported fixture entry: %s", relative)
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		return os.WriteFile(target, content, info.Mode().Perm())
	})
	if err != nil {
		os.RemoveAll(workspace)
		return "", fmt.Errorf("copy SWE fixture: %w", err)
	}
	return workspace, nil
}

func runGit(workspace string, arguments ...string) error {
	command := exec.Command("git", arguments...)
	command.Dir = workspace
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("git %s: %w: %s", strings.Join(arguments, " "), err, strings.TrimSpace(string(output)))
	}
	return nil
}

func gitDiff(workspace string) (string, error) {
	command := exec.Command("git", "diff", "--binary", "--no-ext-diff", "--")
	command.Dir = workspace
	output, err := command.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("generate git diff: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return string(output), nil
}

func runSWECommand(ctx context.Context, workspace, commandText string) (bool, bool, string, error) {
	home := filepath.Join(workspace, ".eval-home")
	cache := filepath.Join(workspace, ".eval-cache")
	goCache := filepath.Join(os.TempDir(), "fastclaw-eval-go-build")
	if err := os.MkdirAll(home, 0o700); err != nil {
		return false, false, "", err
	}
	if err := os.MkdirAll(cache, 0o700); err != nil {
		return false, false, "", err
	}
	if err := os.MkdirAll(goCache, 0o700); err != nil {
		return false, false, "", err
	}
	command := exec.CommandContext(ctx, "/bin/sh", "-c", commandText)
	command.Dir = workspace
	command.Env = append(
		os.Environ(),
		"HOME="+home,
		"GOCACHE="+goCache,
		"XDG_CACHE_HOME="+cache,
	)
	var output bytes.Buffer
	command.Stdout = &output
	command.Stderr = &output
	err := command.Run()
	text := truncateSWEOutput(output.String())
	if ctx.Err() != nil {
		return false, false, text, ctx.Err()
	}
	if err == nil {
		return true, true, text, nil
	}
	var exitError *exec.ExitError
	if errors.As(err, &exitError) {
		return true, false, text, nil
	}
	return false, false, text, err
}

func truncateSWEOutput(output string) string {
	if len(output) <= maxSWETestOutputBytes {
		return output
	}
	return output[:maxSWETestOutputBytes] + "\n...[truncated]"
}

func sweTestMessage(executed, passed bool, err error) string {
	switch {
	case passed:
		return ""
	case !executed && err != nil:
		return "tests could not execute: " + err.Error()
	case !executed:
		return "tests could not execute"
	default:
		return "test command failed"
	}
}

func sweErrorAttempt(attempt int, startedAt time.Time, err error) AttemptResult {
	return AttemptResult{
		Attempt:   attempt,
		Kind:      "swe",
		Error:     err.Error(),
		LatencyMS: milliseconds(time.Since(startedAt)),
	}
}

func sweRepetitions(suite SWESuite, evalCase SWECase, override int) int {
	if override > 0 {
		return override
	}
	if evalCase.Repetitions > 0 {
		return evalCase.Repetitions
	}
	if suite.Defaults.Repetitions > 0 {
		return suite.Defaults.Repetitions
	}
	return 1
}

func sweTimeout(suite SWESuite, evalCase SWECase, override time.Duration) time.Duration {
	if override > 0 {
		return override
	}
	if evalCase.Timeout.Value() > 0 {
		return evalCase.Timeout.Value()
	}
	if suite.Defaults.Timeout.Value() > 0 {
		return suite.Defaults.Timeout.Value()
	}
	return defaultTimeout
}

func WriteSWEPredictions(writer io.Writer, report Report) error {
	encoder := json.NewEncoder(writer)
	for _, evalCase := range report.Cases {
		prediction := SWEPrediction{InstanceID: evalCase.ID}
		if len(evalCase.Attempts) > 0 {
			prediction.ModelNameOrPath = evalCase.Attempts[0].Model
			prediction.ModelPatch = evalCase.Attempts[0].Patch
		}
		if err := encoder.Encode(prediction); err != nil {
			return err
		}
	}
	return nil
}
