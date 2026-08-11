package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"time"

	"github.com/spf13/cobra"

	evalpkg "github.com/fastclaw-ai/fastclaw/internal/eval"
)

func evalCmd() *cobra.Command {
	command := &cobra.Command{
		Use:   "eval",
		Short: "Run and compare agent capability evaluations",
	}
	command.AddCommand(evalRunCmd())
	command.AddCommand(evalCompareCmd())
	command.AddCommand(evalBFCLCmd())
	command.AddCommand(evalTauCmd())
	command.AddCommand(evalSWECmd())
	command.AddCommand(evalMultiAgentCmd())
	return command
}

func evalMultiAgentCmd() *cobra.Command {
	command := &cobra.Command{
		Use:   "multiagent",
		Short: "Run MultiAgentBench-style coordination evaluations",
	}
	command.AddCommand(evalMultiAgentRunCmd())
	command.AddCommand(evalMultiAgentTenantCmd())
	return command
}

func evalMultiAgentRunCmd() *cobra.Command {
	var (
		baseURL     string
		apiKey      string
		agentID     string
		repetitions int
		timeout     time.Duration
		format      string
		output      string
		failUnder   float64
		caseIDs     []string
	)
	command := &cobra.Command{
		Use:   "run <suite.yaml>",
		Short: "Run fair-baseline and fault-aware multi-agent evaluation",
		Args:  cobra.ExactArgs(1),
		RunE: func(command *cobra.Command, args []string) error {
			if format != "text" && format != "json" {
				return fmt.Errorf("unsupported output format %q", format)
			}
			if failUnder < 0 || failUnder > 1 {
				return errors.New("--fail-under must be between 0 and 1")
			}
			if repetitions < 0 {
				return errors.New("--repetitions cannot be negative")
			}
			if timeout < 0 {
				return errors.New("--timeout cannot be negative")
			}
			suite, err := evalpkg.LoadMultiAgentSuite(args[0])
			if err != nil {
				return err
			}
			runner := evalpkg.MultiAgentRunner{
				Executor: &evalpkg.HTTPExecutor{
					BaseURL: baseURL,
					APIKey:  apiKey,
				},
				Options: evalpkg.RunOptions{
					AgentID:     agentID,
					Repetitions: repetitions,
					Timeout:     timeout,
					CaseIDs:     caseIDs,
				},
			}
			report, err := runner.Run(command.Context(), suite)
			if err != nil {
				return err
			}
			writer, closeWriter, err := evalOutputWriter(command.OutOrStdout(), output)
			if err != nil {
				return err
			}
			defer closeWriter()
			if err := writeEvalReport(writer, format, report); err != nil {
				return err
			}
			if report.Metrics.MATeamSuccessRate < failUnder {
				return fmt.Errorf(
					"multi-agent team success %.3f is below threshold %.3f",
					report.Metrics.MATeamSuccessRate,
					failUnder,
				)
			}
			return nil
		},
	}
	command.Flags().StringVar(&baseURL, "base-url", envOrDefault("FASTCLAW_EVAL_BASE_URL", "http://127.0.0.1:18953"), "FastClaw gateway base URL")
	command.Flags().StringVar(&apiKey, "api-key", os.Getenv("FASTCLAW_API_KEY"), "API key (defaults to FASTCLAW_API_KEY)")
	command.Flags().StringVar(&agentID, "agent-id", "", "override the coordinator agent ID")
	command.Flags().IntVar(&repetitions, "repetitions", 0, "override repetitions per case")
	command.Flags().DurationVar(&timeout, "timeout", 0, "override timeout per attempt")
	command.Flags().StringVar(&format, "format", "text", "output format: text or json")
	command.Flags().StringVarP(&output, "output", "o", "", "write the report to a file")
	command.Flags().Float64Var(&failUnder, "fail-under", 0, "fail when team success is below this 0-1 threshold")
	command.Flags().StringSliceVar(&caseIDs, "case", nil, "run only selected case IDs")
	return command
}

func evalSWECmd() *cobra.Command {
	command := &cobra.Command{
		Use:   "swe",
		Short: "Run deterministic SWE-bench-style repository evaluations",
	}
	command.AddCommand(evalSWERunCmd())
	return command
}

func evalSWERunCmd() *cobra.Command {
	var (
		baseURL           string
		apiKey            string
		agentID           string
		repetitions       int
		timeout           time.Duration
		format            string
		output            string
		predictionsOutput string
		failUnder         float64
	)
	command := &cobra.Command{
		Use:   "run <suite.yaml>",
		Short: "Run virtual-repository tasks with hidden local tests",
		Args:  cobra.ExactArgs(1),
		RunE: func(command *cobra.Command, args []string) error {
			if format != "text" && format != "json" {
				return fmt.Errorf("unsupported output format %q", format)
			}
			if failUnder < 0 || failUnder > 1 {
				return errors.New("--fail-under must be between 0 and 1")
			}
			if repetitions < 0 {
				return errors.New("--repetitions cannot be negative")
			}
			if timeout < 0 {
				return errors.New("--timeout cannot be negative")
			}
			suite, err := evalpkg.LoadSWESuite(args[0])
			if err != nil {
				return err
			}
			runner := evalpkg.SWERunner{
				Executor: &evalpkg.HTTPExecutor{
					BaseURL: baseURL,
					APIKey:  apiKey,
				},
				Options: evalpkg.RunOptions{
					AgentID:     agentID,
					Repetitions: repetitions,
					Timeout:     timeout,
				},
			}
			report, err := runner.Run(command.Context(), suite)
			if err != nil {
				return err
			}
			writer, closeWriter, err := evalOutputWriter(command.OutOrStdout(), output)
			if err != nil {
				return err
			}
			defer closeWriter()
			if err := writeEvalReport(writer, format, report); err != nil {
				return err
			}
			if predictionsOutput != "" {
				predictionWriter, closePredictions, err := evalOutputWriter(io.Discard, predictionsOutput)
				if err != nil {
					return err
				}
				defer closePredictions()
				if err := evalpkg.WriteSWEPredictions(predictionWriter, report); err != nil {
					return err
				}
			}
			if report.Metrics.SWEResolutionRate < failUnder {
				return fmt.Errorf(
					"SWE resolution rate %.3f is below threshold %.3f",
					report.Metrics.SWEResolutionRate,
					failUnder,
				)
			}
			return nil
		},
	}
	command.Flags().StringVar(&baseURL, "base-url", envOrDefault("FASTCLAW_EVAL_BASE_URL", "http://127.0.0.1:18953"), "FastClaw gateway base URL")
	command.Flags().StringVar(&apiKey, "api-key", os.Getenv("FASTCLAW_API_KEY"), "API key (defaults to FASTCLAW_API_KEY)")
	command.Flags().StringVar(&agentID, "agent-id", "", "override the suite agent ID")
	command.Flags().IntVar(&repetitions, "repetitions", 0, "override repetitions per case")
	command.Flags().DurationVar(&timeout, "timeout", 0, "override timeout per attempt")
	command.Flags().StringVar(&format, "format", "text", "output format: text or json")
	command.Flags().StringVarP(&output, "output", "o", "", "write the report to a file")
	command.Flags().StringVar(&predictionsOutput, "predictions-output", "", "write first-attempt patches as SWE-bench JSONL predictions")
	command.Flags().Float64Var(&failUnder, "fail-under", 0, "fail when SWE resolution rate is below this 0-1 threshold")
	return command
}

func evalTauCmd() *cobra.Command {
	command := &cobra.Command{
		Use:   "tau",
		Short: "Run deterministic tau-bench-style stateful evaluations",
	}
	command.AddCommand(evalTauRunCmd())
	return command
}

func evalTauRunCmd() *cobra.Command {
	var (
		baseURL     string
		apiKey      string
		agentID     string
		repetitions int
		timeout     time.Duration
		format      string
		output      string
		failUnder   float64
	)
	command := &cobra.Command{
		Use:   "run <suite.yaml>",
		Short: "Run a scripted-user stateful evaluation suite",
		Args:  cobra.ExactArgs(1),
		RunE: func(command *cobra.Command, args []string) error {
			if format != "text" && format != "json" {
				return fmt.Errorf("unsupported output format %q", format)
			}
			if failUnder < 0 || failUnder > 1 {
				return errors.New("--fail-under must be between 0 and 1")
			}
			if repetitions < 0 {
				return errors.New("--repetitions cannot be negative")
			}
			if timeout < 0 {
				return errors.New("--timeout cannot be negative")
			}
			suite, err := evalpkg.LoadTauSuite(args[0])
			if err != nil {
				return err
			}
			runner := evalpkg.TauRunner{
				Executor: &evalpkg.HTTPExecutor{
					BaseURL: baseURL,
					APIKey:  apiKey,
				},
				Options: evalpkg.RunOptions{
					AgentID:     agentID,
					Repetitions: repetitions,
					Timeout:     timeout,
				},
			}
			report, err := runner.Run(command.Context(), suite)
			if err != nil {
				return err
			}
			writer, closeWriter, err := evalOutputWriter(command.OutOrStdout(), output)
			if err != nil {
				return err
			}
			defer closeWriter()
			if err := writeEvalReport(writer, format, report); err != nil {
				return err
			}
			if report.Metrics.EndToEndTaskSuccess < failUnder {
				return fmt.Errorf(
					"tau end-to-end success %.3f is below threshold %.3f",
					report.Metrics.EndToEndTaskSuccess,
					failUnder,
				)
			}
			return nil
		},
	}
	command.Flags().StringVar(&baseURL, "base-url", envOrDefault("FASTCLAW_EVAL_BASE_URL", "http://127.0.0.1:18953"), "FastClaw gateway base URL")
	command.Flags().StringVar(&apiKey, "api-key", os.Getenv("FASTCLAW_API_KEY"), "API key (defaults to FASTCLAW_API_KEY)")
	command.Flags().StringVar(&agentID, "agent-id", "", "override the suite agent ID")
	command.Flags().IntVar(&repetitions, "repetitions", 0, "override repetitions per case")
	command.Flags().DurationVar(&timeout, "timeout", 0, "override timeout per attempt")
	command.Flags().StringVar(&format, "format", "text", "output format: text or json")
	command.Flags().StringVarP(&output, "output", "o", "", "write the report to a file")
	command.Flags().Float64Var(&failUnder, "fail-under", 0, "fail when end-to-end success is below this 0-1 threshold")
	return command
}

func evalRunCmd() *cobra.Command {
	var (
		baseURL     string
		apiKey      string
		agentID     string
		repetitions int
		timeout     time.Duration
		format      string
		output      string
		failUnder   float64
	)
	command := &cobra.Command{
		Use:   "run <suite.yaml>",
		Short: "Run an evaluation suite against a FastClaw gateway",
		Args:  cobra.ExactArgs(1),
		RunE: func(command *cobra.Command, args []string) error {
			if format != "text" && format != "json" {
				return fmt.Errorf("unsupported output format %q", format)
			}
			if failUnder < 0 || failUnder > 1 {
				return errors.New("--fail-under must be between 0 and 1")
			}
			if repetitions < 0 {
				return errors.New("--repetitions cannot be negative")
			}
			if timeout < 0 {
				return errors.New("--timeout cannot be negative")
			}
			suite, err := evalpkg.LoadSuite(args[0])
			if err != nil {
				return err
			}
			runner := evalpkg.Runner{
				Executor: &evalpkg.HTTPExecutor{
					BaseURL: baseURL,
					APIKey:  apiKey,
				},
				Options: evalpkg.RunOptions{
					AgentID:     agentID,
					Repetitions: repetitions,
					Timeout:     timeout,
				},
			}
			report, err := runner.Run(command.Context(), suite)
			if err != nil {
				return err
			}
			writer, closeWriter, err := evalOutputWriter(command.OutOrStdout(), output)
			if err != nil {
				return err
			}
			defer closeWriter()
			if err := writeEvalReport(writer, format, report); err != nil {
				return err
			}
			if report.Metrics.RunPassRate < failUnder {
				return fmt.Errorf(
					"eval run pass rate %.3f is below threshold %.3f",
					report.Metrics.RunPassRate,
					failUnder,
				)
			}
			return nil
		},
	}
	command.Flags().StringVar(&baseURL, "base-url", envOrDefault("FASTCLAW_EVAL_BASE_URL", "http://127.0.0.1:18953"), "FastClaw gateway base URL")
	command.Flags().StringVar(&apiKey, "api-key", os.Getenv("FASTCLAW_API_KEY"), "API key (defaults to FASTCLAW_API_KEY)")
	command.Flags().StringVar(&agentID, "agent-id", "", "override the suite agent ID")
	command.Flags().IntVar(&repetitions, "repetitions", 0, "override repetitions per case")
	command.Flags().DurationVar(&timeout, "timeout", 0, "override timeout per attempt")
	command.Flags().StringVar(&format, "format", "text", "output format: text or json")
	command.Flags().StringVarP(&output, "output", "o", "", "write the report to a file")
	command.Flags().Float64Var(&failUnder, "fail-under", 0, "fail when run pass rate is below this 0-1 threshold")
	return command
}

func evalCompareCmd() *cobra.Command {
	var (
		format string
		output string
	)
	command := &cobra.Command{
		Use:   "compare <baseline.json> <candidate.json>",
		Short: "Compare two JSON evaluation reports",
		Args:  cobra.ExactArgs(2),
		RunE: func(command *cobra.Command, args []string) error {
			if format != "text" && format != "json" {
				return fmt.Errorf("unsupported output format %q", format)
			}
			baseline, err := evalpkg.LoadReport(args[0])
			if err != nil {
				return err
			}
			candidate, err := evalpkg.LoadReport(args[1])
			if err != nil {
				return err
			}
			comparison, err := evalpkg.Compare(baseline, candidate)
			if err != nil {
				return err
			}
			writer, closeWriter, err := evalOutputWriter(command.OutOrStdout(), output)
			if err != nil {
				return err
			}
			defer closeWriter()
			switch format {
			case "text":
				return evalpkg.WriteComparisonText(writer, comparison)
			case "json":
				return evalpkg.WriteComparisonJSON(writer, comparison)
			default:
				return fmt.Errorf("unsupported output format %q", format)
			}
		},
	}
	command.Flags().StringVar(&format, "format", "text", "output format: text or json")
	command.Flags().StringVarP(&output, "output", "o", "", "write the comparison to a file")
	return command
}

func evalBFCLCmd() *cobra.Command {
	command := &cobra.Command{
		Use:   "bfcl",
		Short: "Import Berkeley Function Calling Leaderboard subsets",
	}
	command.AddCommand(evalBFCLImportCmd())
	return command
}

func evalBFCLImportCmd() *cobra.Command {
	var (
		ids     []string
		limit   int
		agentID string
		output  string
	)
	command := &cobra.Command{
		Use:   "import <questions.jsonl> <answers.jsonl>",
		Short: "Convert BFCL V4 single-turn records into a FastClaw suite",
		Args:  cobra.ExactArgs(2),
		RunE: func(command *cobra.Command, args []string) error {
			suite, err := evalpkg.ImportBFCL(args[0], args[1], evalpkg.BFCLImportOptions{
				IDs:     ids,
				Limit:   limit,
				AgentID: agentID,
			})
			if err != nil {
				return err
			}
			writer, closeWriter, err := evalOutputWriter(command.OutOrStdout(), output)
			if err != nil {
				return err
			}
			defer closeWriter()
			return evalpkg.WriteSuiteYAML(writer, suite)
		},
	}
	command.Flags().StringSliceVar(&ids, "ids", nil, "specific BFCL record IDs")
	command.Flags().IntVar(&limit, "limit", 20, "maximum records when --ids is not set; 0 imports all")
	command.Flags().StringVar(&agentID, "agent-id", "", "set the suite default agent ID")
	command.Flags().StringVarP(&output, "output", "o", "", "write the generated suite to a file")
	return command
}

func writeEvalReport(writer io.Writer, format string, report evalpkg.Report) error {
	switch format {
	case "text":
		return evalpkg.WriteText(writer, report)
	case "json":
		return evalpkg.WriteJSON(writer, report)
	default:
		return fmt.Errorf("unsupported output format %q", format)
	}
}

func evalOutputWriter(defaultWriter io.Writer, path string) (io.Writer, func(), error) {
	if path == "" {
		return defaultWriter, func() {}, nil
	}
	file, err := os.Create(path)
	if err != nil {
		return nil, func() {}, fmt.Errorf("create eval output: %w", err)
	}
	return file, func() {
		_ = file.Close()
	}, nil
}

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
