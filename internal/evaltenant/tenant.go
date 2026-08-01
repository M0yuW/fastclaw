package evaltenant

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"strings"

	"github.com/fastclaw-ai/fastclaw/internal/scope"
	"github.com/fastclaw-ai/fastclaw/internal/store"
	"github.com/fastclaw-ai/fastclaw/internal/users"
)

const (
	Username      = "fastclaw-runtime-benchmark"
	Email         = "runtime-benchmark@local.fastclaw"
	APIKeyName    = "runtime-benchmark-eval"
	CoordinatorID = "bench-coordinator"
)

var AgentIDs = []string{
	CoordinatorID,
	"bench-observer",
	"bench-investigator",
	"bench-policy",
	"bench-operator",
	"finance-source",
	"finance-methodology",
	"finance-governance",
}

type Options struct {
	CoordinatorModel string
	SpecialistModel  string
}

type Result struct {
	UserID      string   `json:"user_id"`
	Username    string   `json:"username"`
	APIKey      string   `json:"api_key"`
	AgentIDs    []string `json:"agent_ids"`
	Suite       string   `json:"suite"`
	GatewayNote string   `json:"gateway_note"`
}

type agentSpec struct {
	ID          string
	Name        string
	Description string
	Soul        string
}

func Provision(ctx context.Context, dataStore store.Store, options Options) (Result, error) {
	if dataStore == nil {
		return Result{}, errors.New("runtime benchmark store is required")
	}
	options.CoordinatorModel = strings.TrimSpace(options.CoordinatorModel)
	options.SpecialistModel = strings.TrimSpace(options.SpecialistModel)
	if options.CoordinatorModel == "" {
		return Result{}, errors.New("coordinator model is required")
	}
	if options.SpecialistModel == "" {
		options.SpecialistModel = options.CoordinatorModel
	}
	coordinatorProvider, err := modelProvider(options.CoordinatorModel)
	if err != nil {
		return Result{}, fmt.Errorf("coordinator model: %w", err)
	}
	specialistProvider, err := modelProvider(options.SpecialistModel)
	if err != nil {
		return Result{}, fmt.Errorf("specialist model: %w", err)
	}
	if coordinatorProvider != specialistProvider {
		return Result{}, fmt.Errorf(
			"coordinator and specialist models must use the same provider key: %q != %q",
			coordinatorProvider,
			specialistProvider,
		)
	}

	accounts, err := users.NewAccounts(dataStore)
	if err != nil {
		return Result{}, err
	}
	account, err := ensureAccount(ctx, dataStore, accounts)
	if err != nil {
		return Result{}, err
	}
	if err := scope.SaveSetting(
		ctx,
		dataStore,
		scope.User,
		account.ID,
		"agents.defaults",
		map[string]any{"model": options.CoordinatorModel},
	); err != nil {
		return Result{}, fmt.Errorf("save benchmark tenant default model: %w", err)
	}

	for _, spec := range benchmarkAgentSpecs() {
		model := options.SpecialistModel
		maxTokens := 2048
		maxIterations := 2
		policyPreset := "no-tools"
		if spec.ID == CoordinatorID {
			model = options.CoordinatorModel
			maxTokens = 4096
			maxIterations = 8
			policyPreset = "delegate-only"
		}
		if err := saveAgent(
			ctx,
			dataStore,
			account.ID,
			spec,
			model,
			maxTokens,
			maxIterations,
			policyPreset,
		); err != nil {
			return Result{}, err
		}
	}

	apiKeys, err := users.NewAPIKeys(dataStore)
	if err != nil {
		return Result{}, err
	}
	token, err := rotateOrCreateAPIKey(ctx, apiKeys, account.ID)
	if err != nil {
		return Result{}, err
	}

	return Result{
		UserID:      account.ID,
		Username:    Username,
		APIKey:      token,
		AgentIDs:    append([]string(nil), AgentIDs...),
		Suite:       "evals/multiagent-runtime-tenant.yaml",
		GatewayNote: "Ensure the provider key is configured at system scope, then restart a running Gateway.",
	}, nil
}

func modelProvider(model string) (string, error) {
	providerKey, modelID, found := strings.Cut(model, "/")
	if !found || strings.TrimSpace(providerKey) == "" || strings.TrimSpace(modelID) == "" {
		return "", errors.New(`model must use "<provider-key>/<model-id>" format`)
	}
	return strings.TrimSpace(providerKey), nil
}

func ensureAccount(
	ctx context.Context,
	dataStore store.Store,
	accounts *users.Accounts,
) (*users.Account, error) {
	record, err := dataStore.GetUserByLogin(ctx, Username)
	if err == nil {
		if record.Status != users.StatusActive {
			return accounts.Update(ctx, record.ID, "", "", users.StatusActive)
		}
		return accounts.Get(ctx, record.ID)
	}
	if !errors.Is(err, store.ErrNotFound) {
		return nil, fmt.Errorf("find runtime benchmark account: %w", err)
	}
	password, err := randomPassword()
	if err != nil {
		return nil, err
	}
	return accounts.Create(
		ctx,
		Username,
		Email,
		password,
		"FastClaw Runtime Benchmark",
		users.RoleUser,
	)
}

func saveAgent(
	ctx context.Context,
	dataStore store.Store,
	userID string,
	spec agentSpec,
	model string,
	maxTokens int,
	maxIterations int,
	policyPreset string,
) error {
	existing, err := dataStore.GetAgent(ctx, spec.ID)
	if err == nil && existing.UserID != userID {
		return fmt.Errorf("benchmark agent ID %q is owned by another tenant", spec.ID)
	}
	if err != nil && !errors.Is(err, store.ErrNotFound) {
		return fmt.Errorf("load benchmark agent %q: %w", spec.ID, err)
	}
	record := &store.AgentRecord{
		ID:     spec.ID,
		UserID: userID,
		Name:   spec.Name,
		Config: map[string]any{
			"description":       spec.Description,
			"model":             model,
			"maxTokens":         maxTokens,
			"temperature":       0.1,
			"maxToolIterations": maxIterations,
			"policy":            policyPreset,
			"requiredIdentityFiles": []string{
				"SOUL.md",
				"IDENTITY.md",
			},
		},
	}
	if existing != nil {
		record.CreatedAt = existing.CreatedAt
	}
	if err := dataStore.SaveAgent(ctx, record); err != nil {
		return fmt.Errorf("save benchmark agent %q: %w", spec.ID, err)
	}
	if err := dataStore.SaveAgentFile(ctx, spec.ID, userID, "SOUL.md", []byte(spec.Soul)); err != nil {
		return fmt.Errorf("save benchmark agent %q SOUL.md: %w", spec.ID, err)
	}
	identity := fmt.Sprintf("# Identity\n\nID: `%s`\nName: %s\n", spec.ID, spec.Name)
	if err := dataStore.SaveAgentFile(ctx, spec.ID, userID, "IDENTITY.md", []byte(identity)); err != nil {
		return fmt.Errorf("save benchmark agent %q IDENTITY.md: %w", spec.ID, err)
	}
	return nil
}

func rotateOrCreateAPIKey(ctx context.Context, apiKeys *users.APIKeys, userID string) (string, error) {
	keys, err := apiKeys.List(ctx, userID)
	if err != nil {
		return "", err
	}
	for _, key := range keys {
		if key.Name != APIKeyName {
			continue
		}
		if err := apiKeys.SetAgents(ctx, key.ID, AgentIDs); err != nil {
			return "", err
		}
		return apiKeys.Rotate(ctx, key.ID)
	}
	_, token, err := apiKeys.Create(ctx, userID, APIKeyName, AgentIDs)
	return token, err
}

func randomPassword() (string, error) {
	var buffer [24]byte
	if _, err := rand.Read(buffer[:]); err != nil {
		return "", fmt.Errorf("generate benchmark account password: %w", err)
	}
	return hex.EncodeToString(buffer[:]), nil
}

func benchmarkAgentSpecs() []agentSpec {
	return []agentSpec{
		{
			ID:          CoordinatorID,
			Name:        "Runtime Benchmark Coordinator",
			Description: "Coordinates fixed-evidence runtime benchmark specialists.",
			Soul: `# Runtime Benchmark Coordinator

You coordinate a controlled evaluation team. You do not possess private case
evidence. For every task:

1. Delegate exactly once to every specialist listed in the task prompt.
2. Include the case marker such as BENCH-01 or FIN-01 in every delegated task.
3. Never delegate to an agent that is not listed.
4. Preserve every evidence ID and material fact exactly as returned.
5. Base the final decision only on specialist evidence.
6. Return sections named Decision, Evidence, and Remediation.
7. A specialist response is a JSON object. Treat its evidence field as the
   only evidence supplied by that specialist.

Do not use prior knowledge to invent missing evidence.`,
		},
		{
			ID:          "bench-observer",
			Name:        "Benchmark Observer",
			Description: "Returns fixed telemetry, audit, test, and account evidence.",
			Soul: specialistSoul("observer", map[string]string{
				"BENCH-01": "OBS-101: checkout errors rose immediately after build 842; database latency stayed normal.",
				"BENCH-02": "OBS-202: 37 of 40 release tests passed; all three failures were admin export role checks.",
				"BENCH-03": "OBS-303: audit log AUD-77 shows service-account svc-report exported 12,400 customer rows at 02:14 UTC.",
				"BENCH-04": "OBS-404: pipeline freshness dropped from 8 minutes to 94 minutes after schema release S-19.",
				"BENCH-05": "OBS-505: account AC-55 is active, has no prior refunds, and was charged twice for order O-900.",
				"BENCH-06": "OBS-606: object-store logs show public reads of bucket customer-exports from 09:10 to 09:42 UTC.",
				"BENCH-07": "OBS-707: peak API load is 820 requests per second and p95 latency is 1.8 seconds.",
				"BENCH-08": "OBS-808: compatibility suite passed 118 of 120 tests; both failures exercise legacy TLS 1.0.",
			}),
		},
		{
			ID:          "bench-investigator",
			Name:        "Benchmark Investigator",
			Description: "Returns fixed log, code, ticket, and root-cause evidence.",
			Soul: specialistSoul("investigator", map[string]string{
				"BENCH-01": "INV-111: checkout logs show a nil pointer in coupon validation introduced by normalization change N-42.",
				"BENCH-02": "INV-212: failed tests prove /admin/export permits viewer-role access after authorization refactor A-7.",
				"BENCH-03": "INV-313: ticket T-88 authorized svc-report for aggregate reports only, not raw customer exports.",
				"BENCH-04": "INV-414: parser logs reject renamed field customer_tier because transform T-31 still expects tier.",
				"BENCH-05": "INV-515: payment trace P-52 contains two successful captures with the same idempotency key.",
				"BENCH-06": "INV-616: infrastructure diff I-63 removed the private ACL while enabling static website hosting.",
				"BENCH-07": "INV-717: profile P-74 attributes 68 percent of request time to synchronous recommendation scoring.",
				"BENCH-08": "INV-818: dependency D-81 fixes CVE-2099-117 but removes TLS 1.0 support.",
			}),
		},
		{
			ID:          "bench-policy",
			Name:        "Benchmark Policy",
			Description: "Returns fixed release, access, refund, privacy, and security rules.",
			Soul: specialistSoul("policy", map[string]string{
				"BENCH-02": "POL-222: release policy RP-4 requires blocking any release with a failed authorization test.",
				"BENCH-03": "POL-323: least-privilege policy LP-2 forbids service accounts from exporting raw customer rows.",
				"BENCH-05": "POL-525: refund policy RF-9 permits immediate refund of a verified duplicate capture below 500 dollars.",
				"BENCH-06": "POL-626: incident policy PI-6 classifies public customer exports as severity one and requires credential rotation.",
				"BENCH-08": "POL-828: security policy SP-8 requires critical CVE remediation within seven days; TLS 1.0 is unsupported.",
			}),
		},
		{
			ID:          "bench-operator",
			Name:        "Benchmark Operator",
			Description: "Returns fixed remediation, rollback, containment, and capacity plans.",
			Soul: specialistSoul("operator", map[string]string{
				"BENCH-01": "OPS-121: rollback build 842 to build 841; expected recovery time is four minutes.",
				"BENCH-02": "OPS-232: rollback authorization refactor A-7 and rerun the three admin export role checks.",
				"BENCH-03": "OPS-333: disable svc-report, revoke its token, and preserve AUD-77 for investigation.",
				"BENCH-04": "OPS-434: deploy transform T-32 with customer_tier mapping, then replay partitions from 06:00 UTC.",
				"BENCH-05": "OPS-535: refund the second capture and attach payment trace P-52 to the customer record.",
				"BENCH-06": "OPS-636: restore private ACL, disable website hosting, rotate object-store credentials, and preserve access logs.",
				"BENCH-07": "OPS-737: move recommendation scoring to an asynchronous worker; projected p95 is 620 milliseconds at 1,000 requests per second.",
				"BENCH-08": "OPS-838: upgrade to D-81 using a 10 percent canary, monitor handshake failures, then expand to 100 percent.",
			}),
		},
		{
			ID:          "finance-source",
			Name:        "Finance Source Specialist",
			Description: "Returns fixed point-in-time filing, event, screening, portfolio, and capex evidence.",
			Soul: specialistSoul("finance-source", map[string]string{
				"FIN-01": "FIL-101: the 2026-07-30 Q2 filing reports services revenue growth of 18 percent and gross-margin expansion of 220 basis points.",
				"FIN-02": "FIL-201: the 2026-07-29 exchange filing states that customer C-17, representing 31 percent of revenue, will not renew its contract.",
				"FIN-03": "EVT-301: the exchange feed and news wire both carry external event ID SSE-688981-77 with the same announcement, inside the 24-hour window.",
				"FIN-04": "DAT-401: candidate X has PE 14 and ROE 16 percent, but free cash flow and debt-to-asset ratio are missing from the retrieved record.",
				"FIN-05": "PTF-501: semiconductors are 62 percent of portfolio weight and the top three semiconductor holdings have average pairwise correlation 0.89.",
				"FIN-06": "FIL-601: the 2026-07-28 exchange filing says full-year capex guidance was reduced from 8 billion to 5 billion yuan.",
			}),
		},
		{
			ID:          "finance-methodology",
			Name:        "Finance Methodology Specialist",
			Description: "Returns fixed thesis, state, screening, stress, and transcript evidence.",
			Soul: specialistSoul("finance-methodology", map[string]string{
				"FIN-01": "THS-111: thesis version 4 names services acceleration as a catalyst and services growth below hardware as an invalidation; the catalyst is confirmed and the invalidation is not observed.",
				"FIN-02": "THS-211: thesis version 2 is invalidated if any customer above 25 percent of revenue is lost; FIL-201 crosses that threshold.",
				"FIN-03": "STA-311: watch WL-7 already has alert FA-9 for that fingerprint with duplicate_count 1 and status new.",
				"FIN-04": "MET-411: require_complete is true, so every metric used by the screen must be present and missing fields cannot be treated as passing.",
				"FIN-05": "STR-511: the configured sector-shock scenario estimates a 17 percent portfolio drawdown, compared with the 10 percent risk limit.",
				"FIN-06": "TRN-611: the 2026-07-29 official call transcript says the original 8-billion-yuan expansion plan remains unchanged.",
			}),
		},
		{
			ID:          "finance-governance",
			Name:        "Finance Governance Specialist",
			Description: "Returns fixed bounded decision, policy, and research-state controls.",
			Soul: specialistSoul("finance-governance", map[string]string{
				"FIN-01": "RSK-121: record a positive upgrade review, move conviction from 3 to 4, retain active status, and require expected_version 4; no trade is authorized.",
				"FIN-02": "RSK-221: persist decision invalidate with expected_version 2, set status invalidated, and request a fresh evidence review without estimating a target price.",
				"FIN-03": "POL-321: do not create a second alert; increment FA-9 duplicate_count to 2 and last_seen_at, then run thesis review only once.",
				"FIN-04": "RSK-421: reject candidate X as insufficient_data, exclude it from the ranking, and request source refresh instead of estimating values.",
				"FIN-05": "RSK-521: propose a staged rebalance that reduces semiconductor weight below 45 percent, then rerun concentration and stress checks before any execution; returns are not guaranteed.",
				"FIN-06": "RSK-621: mark an explicit contradiction, choose needs_review, keep conviction unchanged, and request clarification before any upgrade or downgrade.",
			}),
		},
	}
}

func specialistSoul(role string, evidence map[string]string) string {
	var builder strings.Builder
	displayRole := strings.ToUpper(role[:1]) + role[1:]
	fmt.Fprintf(&builder, "# Runtime Benchmark %s\n\n", displayRole)
	builder.WriteString(`You are a controlled benchmark specialist. You have no tools. Do not use
outside knowledge. Read the case marker in the delegated task and return
exactly one compact JSON object with fields case_id, role, and evidence. Copy
the matching evidence line below verbatim into evidence. Do not reveal evidence
for other cases. If the marker is absent or unknown, return
{"case_id":"","role":"` + role + `","evidence":"NO_MATCHING_EVIDENCE"}.

`)
	caseIDs := make([]string, 0, len(evidence))
	for caseID := range evidence {
		caseIDs = append(caseIDs, caseID)
	}
	sort.Strings(caseIDs)
	for _, caseID := range caseIDs {
		if report := evidence[caseID]; report != "" {
			fmt.Fprintf(
				&builder,
				"- %s => {\"case_id\":%q,\"role\":%q,\"evidence\":%q}\n",
				caseID,
				caseID,
				role,
				report,
			)
		}
	}
	return builder.String()
}
