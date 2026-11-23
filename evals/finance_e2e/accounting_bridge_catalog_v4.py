"""Source-auditor-defined signed accounting identities for free v4 preparation.

These are development-case formulas, not held-out quality outcomes. Each one
must continue to match its issuer auditor and both frozen SEC periods.
"""

BRIDGES = {
    "ALLY": [
        ("pre-tax income", "gaap_pre_tax_income", {
            "gaap_total_net_revenue": 1,
            "gaap_provision_for_credit_losses": -1,
            "gaap_noninterest_expense": -1,
        }),
    ],
    "CBOE": [
        ("operating income", "gaap_operating_income", {
            "gaap_net_revenue": 1,
            "gaap_total_operating_expenses": -1,
        }),
    ],
    "IBKR": [
        ("pre-tax income", "gaap_income_before_taxes", {
            "gaap_total_net_revenues": 1,
            "gaap_total_noninterest_expenses": -1,
        }),
        ("consolidated net income", "gaap_consolidated_net_income", {
            "gaap_income_before_taxes": 1,
            "gaap_income_tax_expense": -1,
        }),
        ("net income available to common", "gaap_net_income_available_common", {
            "gaap_consolidated_net_income": 1,
            "gaap_net_income_noncontrolling_interests": -1,
        }),
    ],
    "ICE": [
        ("operating income", "gaap_operating_income", {
            "gaap_revenue_less_transaction_expenses": 1,
            "gaap_total_operating_expenses": -1,
        }),
    ],
    "MSCI": [
        ("operating income", "gaap_operating_income", {
            "gaap_operating_revenues": 1,
            "gaap_total_operating_expenses": -1,
        }),
        ("pre-tax income", "gaap_income_before_taxes", {
            "gaap_operating_income": 1,
            "gaap_other_expense_net": -1,
        }),
        ("net income", "gaap_net_income", {
            "gaap_income_before_taxes": 1,
            "gaap_provision_for_income_taxes": -1,
        }),
    ],
    "SCHW": [
        ("pre-tax income", "gaap_income_before_taxes", {
            "gaap_total_net_revenues": 1,
            "gaap_expenses_excluding_interest": -1,
        }),
        ("net income", "gaap_net_income", {
            "gaap_income_before_taxes": 1,
            "gaap_taxes_on_income": -1,
        }),
        ("net income available to common", "gaap_net_income_available_to_common", {
            "gaap_net_income": 1,
            "gaap_preferred_stock_dividends_and_other": -1,
        }),
    ],
    "WU": [
        ("operating income", "gaap_operating_income", {
            "gaap_revenues": 1,
            "gaap_total_expenses": -1,
        }),
        ("pre-tax income", "gaap_income_before_income_taxes", {
            "gaap_operating_income": 1,
            "gaap_total_other_expense_net_signed": 1,
        }),
        ("net income", "gaap_net_income", {
            "gaap_income_before_income_taxes": 1,
            "gaap_provision_for_income_taxes": -1,
        }),
    ],
    "FIS": [
        ("continuing-operations income", "gaap_net_earnings_continuing_operations", {
            "gaap_earnings_before_taxes_and_equity": 1,
            "gaap_provision_for_income_taxes": -1,
            "gaap_equity_method_investment_earnings_net_of_tax": 1,
        }),
    ],
    "GPN": [
        ("operating income", "gaap_operating_income", {
            "gaap_revenues": 1,
            "gaap_cost_of_service": -1,
            "gaap_selling_general_administrative": -1,
            "gaap_disposition_gain_as_negative_expense": -1,
        }),
        ("net income", "gaap_net_income", {
            "gaap_income_continuing_operations": 1,
            "gaap_income_discontinued_operations": 1,
        }),
        ("attributable net income", "gaap_net_income_attributable_to_global_payments", {
            "gaap_net_income": 1,
            "gaap_net_income_attributable_to_noncontrolling_interests_signed": 1,
        }),
    ],
    "NDAQ": [
        ("operating income", "gaap_operating_income", {
            "gaap_revenue_less_transaction_expenses": 1,
            "gaap_total_operating_expenses": -1,
        }),
    ],
    "FOUR": [
        ("gross revenue less network fees", "non_gaap_gross_revenue_less_network_fees", {
            "gaap_gross_revenue": 1,
            "gaap_network_fees_signed": 1,
        }),
        ("attributable net income", "gaap_net_income_attributable_to_shift4", {
            "gaap_net_income": 1,
            "gaap_noncontrolling_income_signed": 1,
        }),
    ],
}
