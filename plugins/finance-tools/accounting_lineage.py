"""Experimental structured accounting-lineage validation for ledger writes.

Only trusted, source-audited fact metadata may be passed as ``facts``. The
validator does not parse free-form model prose or prove SEC provenance.
"""

from typing import Any


ALLOWED_DRIVER_LINES = {
    "gross_margin": {"cost_of_sales", "contra_revenue", "revenue_mix"},
    "operating_margin": {
        "cost_of_sales", "contra_revenue", "revenue_mix", "operating_expense"
    },
    "pretax_income": {
        "revenue", "cost_of_sales", "contra_revenue", "revenue_mix",
        "operating_expense", "nonoperating",
    },
    "net_income": {
        "revenue", "cost_of_sales", "contra_revenue", "revenue_mix",
        "operating_expense", "nonoperating", "income_tax",
    },
    "diluted_eps_gaap": {
        "revenue", "cost_of_sales", "contra_revenue", "revenue_mix",
        "operating_expense", "nonoperating", "income_tax",
    },
}
CLAIM_STRENGTHS = {"directly_stated", "consistent_with", "unresolved"}


class ClaimValidationError(ValueError):
    """A structured causal claim is unsupported by the trusted fact catalog."""


def validate_causal_claims(
    facts: dict[str, dict[str, Any]], claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate every driver in a structured claim before it is published.

    A line-compatible item only makes an unquantified ``consistent_with``
    statement permissible. ``directly_stated`` also needs an explicit source
    link to the target. A numerical attribution needs a separately audited
    reconciliation; a bare charge amount is never one.
    """
    validated = []
    for index, claim in enumerate(claims):
        target = claim.get("target_metric")
        strength = claim.get("strength")
        drivers = claim.get("driver_fact_ids")
        if target not in ALLOWED_DRIVER_LINES:
            allowed = ", ".join(sorted(ALLOWED_DRIVER_LINES))
            raise ClaimValidationError(
                f"claim[{index}]: unsupported target_metric {target!r}; "
                f"supported targets: {allowed}. If the packet has no source-backed "
                "driver for a supported target, send causal_claims=[] instead "
                "of guessing a target or using a fact as its own cause."
            )
        if strength not in CLAIM_STRENGTHS:
            allowed = ", ".join(sorted(CLAIM_STRENGTHS))
            raise ClaimValidationError(
                f"claim[{index}]: invalid strength {strength!r}; "
                f"supported values: {allowed}"
            )
        if (not isinstance(drivers, list)
                or any(not isinstance(driver, str) or not driver for driver in drivers)
                or len(drivers) != len(set(drivers))):
            raise ClaimValidationError(f"claim[{index}]: invalid driver_fact_ids")
        for fact_id in drivers:
            if fact_id not in facts:
                raise ClaimValidationError(f"claim[{index}]: unknown fact_id {fact_id}")
        if strength == "unresolved":
            if claim.get("attributed_change_percentage_points") is not None:
                raise ClaimValidationError(f"claim[{index}]: unresolved claim is quantified")
            validated.append(claim)
            continue
        if not drivers:
            raise ClaimValidationError(f"claim[{index}]: supported claim needs drivers")
        for fact_id in drivers:
            fact = facts[fact_id]
            if fact.get("statement_line") not in ALLOWED_DRIVER_LINES[target]:
                raise ClaimValidationError(
                    f"claim[{index}]: {fact_id} is not a {target} driver"
                )
            if strength == "directly_stated" and target not in fact.get(
                "source_explicit_targets", []
            ):
                raise ClaimValidationError(
                    f"claim[{index}]: {fact_id} lacks source-explicit target link"
                )
        if claim.get("attributed_change_percentage_points") is not None and not all(
            target in facts[fact_id].get("reconciled_targets", [])
            for fact_id in drivers
        ):
            raise ClaimValidationError(
                f"claim[{index}]: numerical attribution lacks reconciliation"
            )
        validated.append(claim)
    return validated


def render_guarded_rationale(
    decision: str,
    impact: str,
    observed_metrics: dict[str, dict[str, Any]],
    claims: list[dict[str, Any]],
) -> str:
    """Create a factual persisted rationale without using untrusted draft prose."""
    facts = "; ".join(
        f"{name}={item['value']} {item['unit']} [{item['fact_id']}]"
        for name, item in sorted(observed_metrics.items())
    )
    parts = [f"Guarded review recorded decision={decision}, impact={impact}.",
             f"Stored event facts: {facts}."]
    if not claims:
        parts.append("No source-backed causal attribution was recorded.")
    for claim in claims:
        target = claim["target_metric"]
        drivers = ", ".join(claim["driver_fact_ids"]) or "none identified"
        if claim["strength"] == "unresolved":
            parts.append(f"Attribution for {target} is unresolved; proposed drivers: {drivers}.")
        elif claim["strength"] == "consistent_with":
            parts.append(
                f"Facts {drivers} are line-compatible with {target}; "
                "their numerical contribution is not established."
            )
        else:
            parts.append(
                f"The trusted source explicitly links facts {drivers} to {target}; "
                "their numerical contribution is not established unless separately reconciled."
            )
    parts.append("This guard validates stated causal lineage, not the investment merit of the decision.")
    return " ".join(parts)
