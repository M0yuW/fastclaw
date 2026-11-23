package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"github.com/spf13/cobra"

	"github.com/fastclaw-ai/fastclaw/internal/evaltenant"
)

func evalMultiAgentTenantCmd() *cobra.Command {
	command := &cobra.Command{
		Use:   "tenant",
		Short: "Provision fixed real-agent runtime benchmark tenants",
	}
	command.AddCommand(evalMultiAgentTenantProvisionCmd())
	return command
}

func evalMultiAgentTenantProvisionCmd() *cobra.Command {
	var coordinatorModel string
	var specialistModel string
	var output string
	command := &cobra.Command{
		Use:   "provision",
		Short: "Create or refresh the fixed runtime benchmark tenant",
		RunE: func(command *cobra.Command, _ []string) error {
			dataStore, err := openStoreFromEnv()
			if err != nil {
				return err
			}
			defer dataStore.Close()

			result, err := evaltenant.Provision(command.Context(), dataStore, evaltenant.Options{
				CoordinatorModel: coordinatorModel,
				SpecialistModel:  specialistModel,
			})
			if err != nil {
				return err
			}
			writer, closeWriter, err := tenantCredentialWriter(command.OutOrStdout(), output)
			if err != nil {
				return err
			}
			defer closeWriter()
			encoder := json.NewEncoder(writer)
			encoder.SetIndent("", "  ")
			if err := encoder.Encode(result); err != nil {
				return fmt.Errorf("write benchmark tenant result: %w", err)
			}
			return nil
		},
	}
	command.Flags().StringVar(&coordinatorModel, "coordinator-model", "", "model configured for bench-coordinator")
	command.Flags().StringVar(&specialistModel, "specialist-model", "", "model configured for specialists (defaults to coordinator model)")
	command.Flags().StringVarP(&output, "output", "o", "", "write tenant credentials to a file")
	_ = command.MarkFlagRequired("coordinator-model")
	return command
}

func tenantCredentialWriter(defaultWriter io.Writer, path string) (io.Writer, func(), error) {
	if path == "" {
		return defaultWriter, func() {}, nil
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return nil, func() {}, fmt.Errorf("create benchmark credential output: %w", err)
	}
	if err := file.Chmod(0o600); err != nil {
		file.Close()
		return nil, func() {}, fmt.Errorf("secure benchmark credential output: %w", err)
	}
	return file, func() {
		_ = file.Close()
	}, nil
}
