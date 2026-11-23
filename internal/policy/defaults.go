package policy

// DefaultPolicy returns a permissive policy that allows everything.
func DefaultPolicy() *Policy {
	return &Policy{
		Name:        "permissive",
		Description: "Allows all operations (default)",
		Network: NetPolicy{
			Mode: "permissive",
		},
		Tools: ToolsPolicy{
			Allow: []string{"*"},
		},
	}
}

// RestrictedPolicy returns a locked-down policy that denies everything by default.
func RestrictedPolicy() *Policy {
	return &Policy{
		Name:        "restricted",
		Description: "Denies all operations unless explicitly allowed",
		Filesystem: FSPolicy{
			DenyWrite: []string{"/etc/*", "/usr/*", "/bin/*", "/sbin/*", "/var/*"},
			DenyRead:  []string{"/etc/shadow", "/etc/passwd"},
		},
		Network: NetPolicy{
			Mode: "none",
		},
		Tools: ToolsPolicy{
			Deny: []string{"exec"},
		},
		Resources: ResPolicy{
			MaxCPU:      "1",
			MaxMemory:   "256m",
			ExecTimeout: 30,
		},
	}
}

// StandardPolicy returns sensible defaults.
func StandardPolicy() *Policy {
	return &Policy{
		Name:        "standard",
		Description: "Sensible defaults: no write to system dirs, allowlist network",
		Filesystem: FSPolicy{
			DenyWrite: []string{"/etc/*", "/usr/*", "/bin/*", "/sbin/*"},
			DenyRead:  []string{"/etc/shadow"},
		},
		Network: NetPolicy{
			Mode: "permissive",
		},
		Tools: ToolsPolicy{
			Allow: []string{"*"},
		},
		Resources: ResPolicy{
			MaxCPU:      "2",
			MaxMemory:   "512m",
			ExecTimeout: 60,
		},
	}
}

// NoToolsPolicy is for agents that must answer only from their supplied
// context, without runtime side effects or tool-driven evidence lookup.
func NoToolsPolicy() *Policy {
	return &Policy{
		Name:        "no-tools",
		Description: "Disables every tool",
		Network: NetPolicy{
			Mode: "none",
		},
		Tools: ToolsPolicy{
			Deny: []string{"*"},
		},
	}
}

// DelegateOnlyPolicy limits an orchestrator to sub-agent delegation.
func DelegateOnlyPolicy() *Policy {
	return &Policy{
		Name:        "delegate-only",
		Description: "Allows only spawn_subagent",
		Network: NetPolicy{
			Mode: "none",
		},
		Tools: ToolsPolicy{
			Allow: []string{"spawn_subagent"},
		},
	}
}

// FinanceReviewOnlyPolicy permits the narrow, non-trading research review
// workflow used by the SEC event-to-thesis integration experiment.
func FinanceReviewOnlyPolicy() *Policy {
	return &Policy{
		Name:        "finance-review-only",
		Description: "Allows only finance thesis and alert review tools",
		Network: NetPolicy{
			Mode: "none",
		},
		Tools: ToolsPolicy{
			Allow: []string{
				"finance-tools__thesis_get",
				"finance-tools__thesis_match_event",
				"finance-tools__thesis_record_review",
				"finance-tools__alert_list",
				"finance-tools__alert_update",
			},
		},
	}
}

// FinanceWorkflowPilotPolicy permits non-trading finance workflows while
// denying shell, network, delegation, and event ingestion from the agent.
// Source packets are inserted by trusted fixture setup, not model calls.
func FinanceWorkflowPilotPolicy() *Policy {
	return &Policy{
		Name:        "finance-workflow-pilot",
		Description: "Allows bounded research, screening, and risk tools without trading or event ingestion",
		Network:     NetPolicy{Mode: "none"},
		Tools: ToolsPolicy{Allow: []string{
			"finance-tools__screen_stocks",
			"finance-tools__portfolio_risk",
			"finance-tools__portfolio_policy_bound",
			"finance-tools__thesis_save",
			"finance-tools__thesis_get",
			"finance-tools__thesis_list",
			"finance-tools__thesis_match_event",
			"finance-tools__thesis_record_review",
			"finance-tools__alert_list",
			"finance-tools__alert_update",
		}},
	}
}
