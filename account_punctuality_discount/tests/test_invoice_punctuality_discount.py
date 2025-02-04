# Copyright (C) 2022 - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoicePunctualityDiscount(AccountTestInvoicingCommon):
    """
    Test Invoice Punctuality Discount
    """

    @classmethod
    def setUpClass(
        cls, chart_template_ref="l10n_br_coa_generic.l10n_br_coa_generic_template"
    ):
        """Extend default setUpClass"""
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.partner_a.update({"punctuality_discount": 10})

    def test_onchange_partner_id_sets_discount(self):
        invoice = self.env["account.move"].new({"partner_id": self.partner_a.id})
        invoice._onchange_partner_id()
        self.assertEqual(invoice.invoice_punctuality_discount, 10)

    def test_punctuality_discount_cannot_be_negative(self):
        with self.assertRaises(UserError):
            self.env["account.move"].create(
                {"partner_id": self.partner_a.id, "invoice_punctuality_discount": -5}
            )

    def test_punctuality_discount_cannot_exceed_100(self):
        with self.assertRaises(UserError):
            self.env["account.move"].create(
                {"partner_id": self.partner_a.id, "invoice_punctuality_discount": 105}
            )

    def test_punctuality_discount_passes_to_invoice(self):
        sale_order = self.env["sale.order"].create(
            {"partner_id": self.partner_a.id, "punctuality_discount": 10}
        )
        invoice_vals = sale_order._prepare_invoice()
        self.assertEqual(
            invoice_vals.get("invoice_punctuality_discount"),
            10,
        )
