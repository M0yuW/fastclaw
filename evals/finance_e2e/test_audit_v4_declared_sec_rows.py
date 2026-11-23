import json
import unittest
from pathlib import Path

import audit_v4_declared_sec_rows as subject


PACKET = Path(__file__).parent / "seic_v4_declared_source_packet.json"
MKTX_PACKET = Path(__file__).parent / "mktx_v4_declared_source_packet.json"
FDS_PACKET = Path(__file__).parent / "fds_v4_declared_source_packet.json"
RELY_PACKET = Path(__file__).parent / "rely_v4_declared_source_packet.json"
CPAY_PACKET = Path(__file__).parent / "cpay_v4_declared_source_packet.json"
TFC_PACKET = Path(__file__).parent / "tfc_v4_declared_source_packet.json"
FITB_PACKET = Path(__file__).parent / "fitb_v4_declared_source_packet.json"
USB_PACKET = Path(__file__).parent / "usb_v4_declared_source_packet.json"
C_PACKET = Path(__file__).parent / "c_v4_declared_source_packet.json"
FLYW_PACKET = Path(__file__).parent / "flyw_v4_declared_source_packet.json"
EVTC_PACKET = Path(__file__).parent / "evtc_v4_declared_source_packet.json"
SPGI_PACKET = Path(__file__).parent / "spgi_v4_declared_source_packet.json"
TRU_PACKET = Path(__file__).parent / "tru_v4_declared_source_packet.json"
NAVI_PACKET = Path(__file__).parent / "navi_v4_declared_source_packet.json"
RKT_PACKET = Path(__file__).parent / "rkt_v4_declared_source_packet.json"
LPLA_PACKET = Path(__file__).parent / "lpla_v4_declared_source_packet.json"


class DeclaredRowsAuditTests(unittest.TestCase):
    def packet(self):
        return json.loads(PACKET.read_text())

    def test_seic_frozen_source_rows_and_signed_identities(self):
        result = subject.audit(self.packet())
        self.assertEqual(result["selected_source_rows"], 35)
        self.assertEqual(result["declared_identities"], 9)
        self.assertEqual(result["model_observations"], 0)

    def test_changed_raw_cell_rejected(self):
        packet = self.packet()
        packet["event"]["facts"][0]["raw"] = "$461,965"
        with self.assertRaisesRegex(ValueError, "source row/cell differs"):
            subject.audit(packet)

    def test_changed_period_anchor_rejected(self):
        packet = self.packet()
        packet["event"]["anchors"][1]["contains"] = "June 30"
        with self.assertRaisesRegex(ValueError, "period/unit anchor differs"):
            subject.audit(packet)

    def test_missing_one_time_gain_breaks_signed_bridge(self):
        packet = self.packet()
        rule = next(rule for rule in packet["baseline"]["facts"]
                    if rule["metric"] == "gain_on_sale_of_business")
        packet["baseline"]["facts"].remove(rule)
        with self.assertRaisesRegex(ValueError, "identity component/sign invalid"):
            subject.audit(packet)

    def test_mktx_notable_item_bridge_and_split_negative_cell(self):
        result = subject.audit(json.loads(MKTX_PACKET.read_text()))
        self.assertEqual(result["symbol"], "MKTX")
        self.assertEqual(result["selected_source_rows"], 32)
        self.assertEqual(result["declared_identities"], 10)

    def test_mktx_split_parenthesis_tamper_rejected(self):
        packet = json.loads(MKTX_PACKET.read_text())
        item = next(x for x in packet["baseline"]["facts"]
                    if x["metric"] == "non_gaap_tax_impact_signed")
        item["closing_cell"] = 5
        with self.assertRaisesRegex(ValueError, "split negative cell differs"):
            subject.audit(packet)

    def test_fds_adjacent_fiscal_quarters(self):
        packet = json.loads(FDS_PACKET.read_text())
        self.assertEqual(packet["baseline"]["period"], "FY2025 Q4 ended 2025-08-31")
        self.assertEqual(packet["event"]["period"], "FY2026 Q1 ended 2025-11-30")
        result = subject.audit(packet)
        self.assertEqual(result["selected_source_rows"], 38)
        self.assertEqual(result["declared_identities"], 10)

    def test_fds_wrong_period_anchor_rejected(self):
        packet = json.loads(FDS_PACKET.read_text())
        packet["event"]["anchors"][2]["contains"] = "August 31"
        with self.assertRaisesRegex(ValueError, "period/unit anchor differs"):
            subject.audit(packet)

    def test_rely_gaap_and_adjusted_ebitda_bridges(self):
        result = subject.audit(json.loads(RELY_PACKET.read_text()))
        self.assertEqual(result["symbol"], "RELY")
        self.assertEqual(result["selected_source_rows"], 46)
        self.assertEqual(result["declared_identities"], 10)

    def test_rely_addback_sign_tamper_rejected(self):
        packet = json.loads(RELY_PACKET.read_text())
        item = next(x for x in packet["event"]["facts"]
                    if x["metric"] == "non_gaap_other_expense_addback_signed")
        item["value"] = "696"
        with self.assertRaisesRegex(ValueError, "numeric interpretation differs"):
            subject.audit(packet)

    def test_cpay_gaap_to_adjusted_bridge(self):
        result = subject.audit(json.loads(CPAY_PACKET.read_text()))
        self.assertEqual(result["symbol"], "CPAY")
        self.assertEqual(result["selected_source_rows"], 41)
        self.assertEqual(result["declared_identities"], 12)

    def test_cpay_tax_adjustment_sign_tamper_rejected(self):
        packet = json.loads(CPAY_PACKET.read_text())
        item = next(x for x in packet["event"]["facts"]
                    if x["metric"] == "adjustment_tax_impact_signed")
        item["value"] = "34739"
        with self.assertRaisesRegex(ValueError, "numeric interpretation differs"):
            subject.audit(packet)

    def test_tfc_fte_nii_and_cross_quarter_comparators(self):
        result = subject.audit(json.loads(TFC_PACKET.read_text()))
        self.assertEqual(result["symbol"], "TFC")
        self.assertEqual(result["selected_source_rows"], 26)
        self.assertEqual(result["cross_source_comparators"], 13)
        self.assertEqual(result["declared_identities"], 2)

    def test_tfc_q2_comparator_tamper_rejected(self):
        packet = json.loads(TFC_PACKET.read_text())
        packet["cross_source_comparators"][1]["raw"] = "0.91"
        with self.assertRaisesRegex(ValueError, "cross-source comparator differs"):
            subject.audit(packet)

    def test_fitb_gaap_income_bridge_and_comparators(self):
        result = subject.audit(json.loads(FITB_PACKET.read_text()))
        self.assertEqual(result["symbol"], "FITB")
        self.assertEqual(result["selected_source_rows"], 30)
        self.assertEqual(result["cross_source_comparators"], 15)
        self.assertEqual(result["declared_identities"], 10)

    def test_fitb_q2_provision_comparator_tamper_rejected(self):
        packet = json.loads(FITB_PACKET.read_text())
        item = next(x for x in packet["cross_source_comparators"]
                    if x["metric"] == "gaap_credit_loss_provision")
        item["raw"] = "174"
        with self.assertRaisesRegex(ValueError, "cross-source comparator differs"):
            subject.audit(packet)

    def test_fitb_tax_sign_tamper_rejected(self):
        packet = json.loads(FITB_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "gaap_net_income")
        rule["components"][1]["sign"] = 1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_usb_taxable_equivalent_and_gaap_bridges(self):
        result = subject.audit(json.loads(USB_PACKET.read_text()))
        self.assertEqual(result["symbol"], "USB")
        self.assertEqual(result["selected_source_rows"], 34)
        self.assertEqual(result["cross_source_comparators"], 15)
        self.assertEqual(result["declared_identities"], 16)

    def test_usb_gaap_pretax_bridge_tamper_rejected(self):
        packet = json.loads(USB_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "gaap_pretax_income")
        rule["components"][1]["sign"] = 1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_usb_cross_quarter_revenue_tamper_rejected(self):
        packet = json.loads(USB_PACKET.read_text())
        item = next(x for x in packet["cross_source_comparators"]
                    if x["metric"] == "fte_total_revenue")
        item["raw"] = "7,005"
        with self.assertRaisesRegex(ValueError, "cross-source comparator differs"):
            subject.audit(packet)

    def test_c_gaap_and_goodwill_adjusted_bridges(self):
        result = subject.audit(json.loads(C_PACKET.read_text()))
        self.assertEqual(result["symbol"], "C")
        self.assertEqual(result["selected_source_rows"], 35)
        self.assertEqual(result["cross_source_comparators"], 14)
        self.assertEqual(result["declared_identities"], 13)

    def test_c_goodwill_adjustment_sign_tamper_rejected(self):
        packet = json.loads(C_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "adjusted_citigroup_net_income")
        rule["components"][1]["sign"] = 1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_c_cross_quarter_cost_of_credit_tamper_rejected(self):
        packet = json.loads(C_PACKET.read_text())
        item = next(x for x in packet["cross_source_comparators"]
                    if x["metric"] == "total_cost_of_credit")
        item["raw"] = "2,873"
        with self.assertRaisesRegex(ValueError, "cross-source comparator differs"):
            subject.audit(packet)

    def test_flyw_gaap_and_rounded_adjusted_ebitda_bridges(self):
        result = subject.audit(json.loads(FLYW_PACKET.read_text()))
        self.assertEqual(result["symbol"], "FLYW")
        self.assertEqual(result["selected_source_rows"], 44)
        self.assertEqual(result["cross_source_comparators"], 0)
        self.assertEqual(result["unit_conversions"], 2)
        self.assertEqual(result["declared_identities"], 10)

    def test_flyw_rounded_unit_conversion_tamper_rejected(self):
        packet = json.loads(FLYW_PACKET.read_text())
        packet["unit_conversions"][0]["source_divisor"] = "100"
        with self.assertRaisesRegex(ValueError, "source unit conversion differs"):
            subject.audit(packet)

    def test_flyw_gaap_tax_sign_tamper_rejected(self):
        packet = json.loads(FLYW_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "baseline" and x["total"] == "gaap_net_income_thousand")
        rule["components"][1]["sign"] = 1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_evtc_gaap_and_adjusted_net_income_bridges(self):
        result = subject.audit(json.loads(EVTC_PACKET.read_text()))
        self.assertEqual(result["symbol"], "EVTC")
        self.assertEqual(result["selected_source_rows"], 48)
        self.assertEqual(result["declared_identities"], 16)

    def test_evtc_tax_benefit_sign_tamper_rejected(self):
        packet = json.loads(EVTC_PACKET.read_text())
        item = next(x for x in packet["event"]["facts"]
                    if x["metric"] == "gaap_income_tax_signed")
        item["value"] = "31"
        with self.assertRaisesRegex(ValueError, "numeric interpretation differs"):
            subject.audit(packet)

    def test_evtc_adjusted_fee_bridge_tamper_rejected(self):
        packet = json.loads(EVTC_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "adjusted_ebitda")
        rule["components"][3]["sign"] = -1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_spgi_gaap_and_adjusted_operating_bridges(self):
        result = subject.audit(json.loads(SPGI_PACKET.read_text()))
        self.assertEqual(result["symbol"], "SPGI")
        self.assertEqual(result["selected_source_rows"], 44)
        self.assertEqual(result["declared_identities"], 14)

    def test_spgi_q2_rounding_tolerance_cannot_hide_material_change(self):
        packet = json.loads(SPGI_PACKET.read_text())
        item = next(x for x in packet["baseline"]["facts"]
                    if x["metric"] == "operating_nongaap_adjustments")
        item["value"] = "198"
        with self.assertRaisesRegex(ValueError, "numeric interpretation differs"):
            subject.audit(packet)

    def test_spgi_q3_adjusted_tax_sign_tamper_rejected(self):
        packet = json.loads(SPGI_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "adjusted_income_tax")
        rule["components"][1]["sign"] = -1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_tru_prior_guidance_vs_realized_q3(self):
        result = subject.audit(json.loads(TRU_PACKET.read_text()))
        self.assertEqual(result["symbol"], "TRU")
        self.assertEqual(result["selected_source_rows"], 44)
        self.assertEqual(result["cross_source_ranges"], 5)
        self.assertEqual(result["declared_identities"], 12)

    def test_tru_guidance_relation_tamper_rejected(self):
        packet = json.loads(TRU_PACKET.read_text())
        packet["cross_source_ranges"][0]["expected_relation"] = "within"
        with self.assertRaisesRegex(ValueError, "guidance range differs"):
            subject.audit(packet)

    def test_tru_guidance_cannot_be_retyped_as_actual(self):
        packet = json.loads(TRU_PACKET.read_text())
        item = next(x for x in packet["baseline"]["facts"]
                    if x["metric"] == "q3_guidance_revenue_low")
        item["basis"] = "GAAP"
        with self.assertRaisesRegex(ValueError, "guidance range differs"):
            subject.audit(packet)

    def test_navi_detailed_exhibits_and_credit_loss_bridges(self):
        result = subject.audit(json.loads(NAVI_PACKET.read_text()))
        self.assertEqual(result["symbol"], "NAVI")
        self.assertEqual(result["selected_source_rows"], 36)
        self.assertEqual(result["cross_source_comparators"], 18)
        self.assertEqual(result["declared_identities"], 14)

    def test_navi_pointer_cannot_replace_detailed_exhibit(self):
        packet = json.loads(NAVI_PACKET.read_text())
        packet["event"]["source_id"] = "HOLDOUT-V4-NAVI-EVENT"
        with self.assertRaisesRegex(ValueError, "source bytes or SEC URL differ"):
            subject.audit(packet)

    def test_navi_credit_provision_sign_tamper_rejected(self):
        packet = json.loads(NAVI_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "gaap_nii_after_provision")
        rule["components"][1]["sign"] = 1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_rkt_gaap_and_adjusted_divergence(self):
        result = subject.audit(json.loads(RKT_PACKET.read_text()))
        self.assertEqual(result["symbol"], "RKT")
        self.assertEqual(result["selected_source_rows"], 64)
        self.assertEqual(result["unit_conversions"], 6)
        self.assertEqual(result["declared_identities"], 18)

    def test_rkt_msr_loss_sign_tamper_rejected(self):
        packet = json.loads(RKT_PACKET.read_text())
        item = next(x for x in packet["event"]["facts"]
                    if x["metric"] == "msr_fair_value_signed")
        item["value"] = "479602"
        with self.assertRaisesRegex(ValueError, "numeric interpretation differs"):
            subject.audit(packet)

    def test_rkt_rounding_tolerance_does_not_hide_large_bridge_error(self):
        packet = json.loads(RKT_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "adjusted_revenue_m")
        rule["components"][1]["sign"] = -1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_lpla_gaap_loss_adjusted_ebitda_and_q2_comparators(self):
        result = subject.audit(json.loads(LPLA_PACKET.read_text()))
        self.assertEqual(result["symbol"], "LPLA")
        self.assertEqual(result["selected_source_rows"], 66)
        self.assertEqual(result["cross_source_comparators"], 12)
        self.assertEqual(result["declared_identities"], 20)

    def test_lpla_acquisition_addback_sign_tamper_rejected(self):
        packet = json.loads(LPLA_PACKET.read_text())
        rule = next(x for x in packet["identities"]
                    if x["role"] == "event" and x["total"] == "adjusted_ebitda")
        rule["components"][1]["sign"] = -1
        with self.assertRaisesRegex(ValueError, "source-defined arithmetic differs"):
            subject.audit(packet)

    def test_lpla_prior_quarter_comparator_tamper_rejected(self):
        packet = json.loads(LPLA_PACKET.read_text())
        item = next(x for x in packet["cross_source_comparators"]
                    if x["metric"] == "adjusted_ebitda")
        item["raw"] = "688,335"
        with self.assertRaisesRegex(ValueError, "cross-source comparator differs"):
            subject.audit(packet)


if __name__ == "__main__":
    unittest.main()
