package evaltenant

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"

	"github.com/fastclaw-ai/fastclaw/internal/scope"
	"github.com/fastclaw-ai/fastclaw/internal/store"
	"github.com/fastclaw-ai/fastclaw/internal/users"
)

const (
	Username             = "fastclaw-runtime-benchmark"
	Email                = "runtime-benchmark@local.fastclaw"
	APIKeyName           = "runtime-benchmark-eval"
	CoordinatorID        = "bench-coordinator"
	FinanceCoordinatorID = "finance-coordinator"
)

var AgentIDs = []string{
	CoordinatorID,
	FinanceCoordinatorID,
	"bench-observer",
	"bench-investigator",
	"bench-policy",
	"bench-operator",
	"finance-source",
	"finance-methodology",
	"finance-governance",
	"finance-retriever",
	"finance-trend",
	"finance-accounting",
	"finance-risk",
	"finance-solo",
}

type Options struct {
	CoordinatorModel string
	SpecialistModel  string
	EvidenceFile     string
}

type Result struct {
	UserID         string   `json:"user_id"`
	Username       string   `json:"username"`
	APIKey         string   `json:"api_key"`
	AgentIDs       []string `json:"agent_ids"`
	Suite          string   `json:"suite"`
	EvidenceSHA256 string   `json:"evidence_sha256,omitempty"`
	GatewayNote    string   `json:"gateway_note"`
}

type agentSpec struct {
	ID          string
	Name        string
	Description string
	Soul        string
	MaxTokens   int
	Thinking    string
}

type runtimeEvidencePack struct {
	Version        int                          `json:"version"`
	Dataset        string                       `json:"dataset"`
	Suite          string                       `json:"suite,omitempty"`
	EvidenceSHA256 string                       `json:"evidence_sha256"`
	Agents         map[string]map[string]string `json:"agents"`
}

var runtimeCaseIDPattern = regexp.MustCompile(`^[A-Z0-9][A-Z0-9-]{2,63}$`)
var runtimeSuitePathPattern = regexp.MustCompile(`^evals/[A-Za-z0-9][A-Za-z0-9._/-]*\.(?:json|ya?ml)$`)

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
	evidence, evidenceSHA256, evidenceSuite, err := loadRuntimeEvidence(options.EvidenceFile)
	if err != nil {
		return Result{}, err
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

	for _, spec := range benchmarkAgentSpecs(evidence) {
		model := options.SpecialistModel
		maxTokens := 2048
		maxIterations := 2
		policyPreset := "no-tools"
		if spec.MaxTokens > 0 {
			maxTokens = spec.MaxTokens
		}
		if spec.ID == CoordinatorID || spec.ID == FinanceCoordinatorID || spec.ID == "finance-solo" {
			model = options.CoordinatorModel
		}
		if spec.ID == CoordinatorID || spec.ID == FinanceCoordinatorID {
			maxTokens = 8192
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
			spec.Thinking,
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

	suite := "evals/multiagent-runtime-tenant.yaml"
	if strings.TrimSpace(options.EvidenceFile) != "" {
		suite = "evals/multiagent-finance-sec-e2e.json"
		if evidenceSuite != "" {
			suite = evidenceSuite
		}
	}
	return Result{
		UserID:         account.ID,
		Username:       Username,
		APIKey:         token,
		AgentIDs:       append([]string(nil), AgentIDs...),
		Suite:          suite,
		EvidenceSHA256: evidenceSHA256,
		GatewayNote:    "Ensure the provider key is configured at system scope, then restart a running Gateway.",
	}, nil
}

func loadRuntimeEvidence(path string) (map[string]map[string]string, string, string, error) {
	path = strings.TrimSpace(path)
	if path == "" {
		return nil, "", "", nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, "", "", fmt.Errorf("read runtime evidence pack: %w", err)
	}
	if len(data) > 4<<20 {
		return nil, "", "", errors.New("runtime evidence pack cannot exceed 4 MiB")
	}
	var pack runtimeEvidencePack
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&pack); err != nil {
		return nil, "", "", fmt.Errorf("decode runtime evidence pack: %w", err)
	}
	if pack.Version != 1 {
		return nil, "", "", errors.New("runtime evidence pack version must be 1")
	}
	if strings.TrimSpace(pack.Dataset) == "" {
		return nil, "", "", errors.New("runtime evidence pack dataset is required")
	}
	pack.Suite = strings.TrimSpace(pack.Suite)
	if pack.Suite != "" &&
		(!runtimeSuitePathPattern.MatchString(pack.Suite) || strings.Contains(pack.Suite, "..")) {
		return nil, "", "", errors.New("runtime evidence pack suite must be a relative evals JSON or YAML path")
	}
	if len(pack.EvidenceSHA256) != sha256.Size*2 {
		return nil, "", "", errors.New("runtime evidence pack evidence_sha256 must contain 64 hexadecimal characters")
	}
	if _, err := hex.DecodeString(pack.EvidenceSHA256); err != nil {
		return nil, "", "", errors.New("runtime evidence pack evidence_sha256 must contain 64 hexadecimal characters")
	}
	allowedAgents := map[string]struct{}{
		"finance-source":      {},
		"finance-methodology": {},
		"finance-governance":  {},
	}
	if len(pack.Agents) != len(allowedAgents) {
		return nil, "", "", errors.New("runtime evidence pack must define all three finance specialists")
	}
	var expectedCases map[string]struct{}
	for agentID, cases := range pack.Agents {
		if _, ok := allowedAgents[agentID]; !ok {
			return nil, "", "", fmt.Errorf("runtime evidence pack cannot override agent %q", agentID)
		}
		if len(cases) == 0 {
			return nil, "", "", fmt.Errorf("runtime evidence pack agent %q has no cases", agentID)
		}
		currentCases := make(map[string]struct{}, len(cases))
		for caseID, response := range cases {
			if !runtimeCaseIDPattern.MatchString(caseID) {
				return nil, "", "", fmt.Errorf("runtime evidence pack has invalid case id %q", caseID)
			}
			if strings.TrimSpace(response) == "" || len(response) > 16<<10 {
				return nil, "", "", fmt.Errorf("runtime evidence pack response for %s/%s must contain 1-16384 bytes", agentID, caseID)
			}
			currentCases[caseID] = struct{}{}
		}
		if expectedCases == nil {
			expectedCases = currentCases
			continue
		}
		if !sameStringSet(expectedCases, currentCases) {
			return nil, "", "", errors.New("runtime evidence pack finance specialists must define identical case sets")
		}
	}
	return pack.Agents, strings.ToLower(pack.EvidenceSHA256), pack.Suite, nil
}

func sameStringSet(left, right map[string]struct{}) bool {
	if len(left) != len(right) {
		return false
	}
	for value := range left {
		if _, ok := right[value]; !ok {
			return false
		}
	}
	return true
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
	thinking string,
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
			"thinking":          thinking,
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

func benchmarkAgentSpecs(runtimeEvidence map[string]map[string]string) []agentSpec {
	financeSourceEvidence := map[string]string{
		"FIN-01": "FIL-101: the 2026-07-30 Q2 filing reports services revenue growth of 18 percent and gross-margin expansion of 220 basis points.",
		"FIN-02": "FIL-201: the 2026-07-29 exchange filing states that customer C-17, representing 31 percent of revenue, will not renew its contract.",
		"FIN-03": "EVT-301: the exchange feed and news wire both carry external event ID SSE-688981-77 with the same announcement, inside the 24-hour window.",
		"FIN-04": "DAT-401: candidate X has PE 14 and ROE 16 percent, but free cash flow and debt-to-asset ratio are missing from the retrieved record.",
		"FIN-05": "PTF-501: semiconductors are 62 percent of portfolio weight and the top three semiconductor holdings have average pairwise correlation 0.89.",
		"FIN-06": "FIL-601: the 2026-07-28 exchange filing says full-year capex guidance was reduced from 8 billion to 5 billion yuan.",
	}
	financeMethodologyEvidence := map[string]string{
		"FIN-01": "THS-111: thesis version 4 names services acceleration as a catalyst and services growth below hardware as an invalidation; the catalyst is confirmed and the invalidation is not observed.",
		"FIN-02": "THS-211: thesis version 2 is invalidated if any customer above 25 percent of revenue is lost; FIL-201 crosses that threshold.",
		"FIN-03": "STA-311: watch WL-7 already has alert FA-9 for that fingerprint with duplicate_count 1 and status new.",
		"FIN-04": "MET-411: require_complete is true, so every metric used by the screen must be present and missing fields cannot be treated as passing.",
		"FIN-05": "STR-511: the configured sector-shock scenario estimates a 17 percent portfolio drawdown, compared with the 10 percent risk limit.",
		"FIN-06": "TRN-611: the 2026-07-29 official call transcript says the original 8-billion-yuan expansion plan remains unchanged.",
	}
	financeGovernanceEvidence := map[string]string{
		"FIN-01": "RSK-121: record a positive upgrade review, move conviction from 3 to 4, retain active status, and require expected_version 4; no trade is authorized.",
		"FIN-02": "RSK-221: persist decision invalidate with expected_version 2, set status invalidated, and request a fresh evidence review without estimating a target price.",
		"FIN-03": "POL-321: do not create a second alert; increment FA-9 duplicate_count to 2 and last_seen_at, then run thesis review only once.",
		"FIN-04": "RSK-421: reject candidate X as insufficient_data, exclude it from the ranking, and request source refresh instead of estimating values.",
		"FIN-05": "RSK-521: propose a staged rebalance that reduces semiconductor weight below 45 percent, then rerun concentration and stress checks before any execution; returns are not guaranteed.",
		"FIN-06": "RSK-621: mark an explicit contradiction, choose needs_review, keep conviction unchanged, and request clarification before any upgrade or downgrade.",
	}
	if runtimeEvidence != nil {
		financeSourceEvidence = runtimeEvidence["finance-source"]
		financeMethodologyEvidence = runtimeEvidence["finance-methodology"]
		financeGovernanceEvidence = runtimeEvidence["finance-governance"]
	}
	return []agentSpec{
		{
			ID:          CoordinatorID,
			Name:        "Runtime Benchmark Coordinator",
			Description: "Coordinates fixed-evidence runtime benchmark specialists.",
			Thinking:    "off",
			Soul: `# Runtime Benchmark Coordinator

You coordinate a controlled evaluation team. You do not possess private case
evidence. For every task:

1. Delegate exactly once to every specialist listed in the task prompt.
2. Include the case marker such as BENCH-01 or FIN-01 in every delegated task.
3. Never delegate to an agent that is not listed.
4. Preserve every evidence ID and material fact exactly as returned.
5. Base the final decision only on specialist evidence.
6. Return the sections requested by the task prompt; otherwise use Decision, Evidence, and Remediation.
7. A specialist response is a JSON object. Treat its evidence field as the
   only evidence supplied by that specialist.
8. Start the final answer with a Verbatim Specialist Evidence section that
   copies each specialist evidence field exactly once, without renaming IDs.
9. Do not introduce a number, ratio, document type, or calculation unless it
   appears verbatim in specialist evidence. Report missing analysis as missing.
10. In the Calculation section, reproduce only calculations returned by the
    methodology specialist. Never show intermediate arithmetic, implied
    differences, margins, shares, or ratios that methodology did not return.
11. Before answering, remove every numeric value that is absent from the three
    specialist evidence fields; describing it as uncertified does not permit it.

Do not use prior knowledge to invent missing evidence.`,
		},
		{
			ID:          FinanceCoordinatorID,
			Name:        "Finance Research Coordinator",
			Description: "Coordinates evidence-bounded financial retrieval and specialist analysis.",
			Thinking:    "off",
			Soul: `# Finance Research Coordinator

You coordinate a controlled financial research pipeline over evidence supplied
in the current task. You do not add facts from prior knowledge.

1. Use exactly one batch spawn_subagent call. Put the common evidence in
   sharedContext once and one concise agentId/task item per specialist in
   delegations; never copy shared evidence into every task.
2. Delegate exactly once to each specialist listed in the current task and to no
   other agent. The runtime executes distinct batch targets concurrently.
3. Give every specialist the same research question and analysis protocol while
   limiting its responsibility to the assigned perspective.
4. Preserve bracketed record IDs, filing dates, period labels, accounting basis,
   uncertainty, and conflicting evidence.
5. Treat the analysis protocol as policy, not as SEC evidence. Apply it only
   when its required source evidence is present.
6. Synthesize specialist reports without copying them wholesale or introducing
   unsupported numbers, calculations, investment recommendations, or trades.

Return the sections required by the current task.`,
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
			Soul:        specialistSoul("finance-source", financeSourceEvidence),
		},
		{
			ID:          "finance-methodology",
			Name:        "Finance Methodology Specialist",
			Description: "Returns fixed thesis, state, screening, stress, and transcript evidence.",
			Soul:        specialistSoul("finance-methodology", financeMethodologyEvidence),
		},
		{
			ID:          "finance-governance",
			Name:        "Finance Governance Specialist",
			Description: "Returns fixed bounded decision, policy, and research-state controls.",
			Soul:        specialistSoul("finance-governance", financeGovernanceEvidence),
		},
		{
			ID:          "finance-retriever",
			Name:        "Finance Retrieval Specialist",
			Description: "Compresses locked point-in-time filing records into an auditable evidence bundle.",
			MaxTokens:   8192,
			Thinking:    "off",
			Soul: `# Finance Retrieval Specialist

You are the retrieval stage of a controlled financial research pipeline. Work
only from the corpus supplied in the current task. Select records that are
material to the question, preserve their bracketed record IDs, source IDs,
filing dates, accounting basis, periods, and exact wording. Retain conflicting
evidence instead of resolving it. Do not calculate, infer a research decision,
use outside knowledge, or recommend a trade. Return only a compact Evidence
Bundle and a Missing Evidence note.`,
		},
		{
			ID:          "finance-trend",
			Name:        "Finance Trend Analyst",
			Description: "Analyzes growth chronology and operating trends from a supplied evidence bundle.",
			MaxTokens:   8192,
			Thinking:    "off",
			Soul: researchAnalystSoul(
				"trend and chronology",
				"reconstruct the observation sequence and assess growth, segment, and channel direction without changing period labels",
			),
		},
		{
			ID:          "finance-accounting",
			Name:        "Finance Accounting Analyst",
			Description: "Audits accounting basis, period comparability, and declared calculations.",
			MaxTokens:   8192,
			Thinking:    "off",
			Soul: researchAnalystSoul(
				"accounting and period audit",
				"separate GAAP, segment, channel, quarterly, and annual measures and show only calculations justified by cited records",
			),
		},
		{
			ID:          "finance-risk",
			Name:        "Finance Risk Analyst",
			Description: "Evaluates downside evidence, contradictions, and bounded research-state controls.",
			MaxTokens:   8192,
			Thinking:    "off",
			Soul: researchAnalystSoul(
				"risk and governance",
				"identify downside evidence and contradictions, then apply only the supplied bounded research-state rules without authorizing a trade",
			),
		},
		{
			ID:          "finance-solo",
			Name:        "Finance Solo Researcher",
			Description: "Provides the same-model monolithic and staged single-agent baselines.",
			MaxTokens:   8192,
			Thinking:    "off",
			Soul: `# Finance Solo Researcher

You are the single-agent control condition for a financial research experiment.
Perform only the stage requested in the current prompt. Work exclusively from
the supplied locked corpus, evidence bundle, or analyst reports. Preserve
bracketed record IDs, distinguish source facts from derived calculations and
bounded research judgments, report missing or conflicting evidence, and never
use outside knowledge or recommend or authorize a trade.`,
		},
	}
}

func researchAnalystSoul(perspective, instruction string) string {
	return fmt.Sprintf(`# Finance %s Specialist

You are a controlled financial research specialist. Work only from evidence
included in the delegated task. Your responsibility is to %s. Cite bracketed
record IDs for every material claim, preserve uncertainty and contradictions,
and do not use outside knowledge or recommend or authorize a trade. Return one
compact specialist report for the coordinator.`, perspective, instruction)
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
