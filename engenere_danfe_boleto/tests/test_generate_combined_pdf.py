# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestGenerateCombinedPDF(TransactionCase):
    def setUp(self):
        super().setUp()

        self.invoice_cef = self.env.ref(
            "l10n_br_account_payment_order." "demo_invoice_payment_order_cef_cnab240"
        )
        self.fiscal_doc = self.env["l10n_br_fiscal.document"].create(
            {
                "document_number": "123456",
                "move_ids": [(6, 0, [self.invoice_cef.id])],
                "issuer": "company",
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
            }
        )

    def test_generate_combined_pdf(self):
        with self.assertRaises(UserError):
            self.invoice_cef.generate_combined_pdf()

        self.invoice_cef.action_post()

        with self.assertRaises(UserError):
            self.invoice_cef.generate_combined_pdf()

        self.invoice_cef.state_edoc = "autorizada"
        self.invoice_cef.generate_combined_pdf()

        self.fiscal_doc.action_document_confirm()
        self.fiscal_doc.view_boleto_pdf()
        self.invoice_cef.generate_combined_pdf()
