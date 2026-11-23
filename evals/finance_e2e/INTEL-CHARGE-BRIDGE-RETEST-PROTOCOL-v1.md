# SEC event causal-attribution source-completeness retest

This is a **separate** five-repeat Intel Q2→Q3 2024 event-to-thesis arm. It does not overwrite the 20-run startup-gated panel. Its purpose is narrow: test whether supplying the SEC exhibit's **line-item composition** in the event packet reduces the previously observed unsupported attribution of the whole USD 15.9 billion bundle to gross-margin compression. It is not a test of a new model, a holdout filing, or general financial-insight reliability.

Keep the same Flash model, agent/template configuration, baseline thesis, original four event metrics, review prompt, source URL/hash, finance tool and judge rubric as in `run_insight_quality_holdout_flash_v1.py`. The only intended treatment is three additional Q3 event metrics and a faithful composition sentence from the same source. No decision, conviction, or target causal conclusion is supplied in the prompt. The added packet facts are frozen in `intel_charge_bridge_v1.json` and must be verified against the locked raw SEC HTML before the first call:

- USD 3.1 billion manufacturing-asset impairment/accelerated depreciation; **substantially all**, not necessarily the whole amount, recognized in cost of sales.
- USD 2.9 billion goodwill and acquired-intangible impairment.
- USD 9.9 billion deferred-tax-asset valuation allowance.
- These three items sum to USD 15.9 billion. The USD 2.8 billion restructuring charge is separately disclosed and must not be folded into that subtotal.

Pre-freeze the runner, packet file and runtime hashes in the manifest. Use five fresh Gateway sessions and ledgers; keep all attempts. Stop before a new call if cumulative estimated cost reaches USD 0.03, or after any request error, unpriced usage, or cost uncertainty. No selective replacement or overwrite.

Execution/fact gate: actual finance-tool review and alert acknowledgement, exact event source/metric retention, correct Q2→Q3 revenue and GAAP gross-margin comparisons, no fabricated source or line-item statement. Inference gate: no association of the **whole** USD 15.9 billion bundle with gross margin; distinguish the cost-of-sales item from goodwill/tax items and avoid claiming that the 3.1 billion fully explains the 20.4-percentage-point margin change. The separate `material margin deterioration` invalidation must not be rewritten as a sustained-weakness condition. Research utility requires a supported thesis implication and a further information need, not just a copied metric list. Apply `INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md` and record each observation.

Descriptive success for this targeted retest requires 5/5 genuine execution and material-fact passes, at least 4/5 inference/risk and research-utility passes, and no critical error. Compare with the original Intel cluster as a **nonrandomized source-completeness contrast**, not causal proof: the Gateway binary also differs by a startup-readiness fix, and stochastic repeats are correlated. Even success here would not establish stability across companies or finance workflows.
