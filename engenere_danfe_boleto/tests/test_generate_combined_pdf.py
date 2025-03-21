# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestGenerateCombinedPDF(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.invoice_cef = cls.env.ref(
            "l10n_br_account_payment_order." "demo_invoice_payment_order_cef_cnab240"
        )
        cls.fiscal_doc = cls.env["l10n_br_fiscal.document"].create(
            {
                "document_number": "123456",
                "move_ids": [(6, 0, [cls.invoice_cef.id])],
                "issuer": "company",
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
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
