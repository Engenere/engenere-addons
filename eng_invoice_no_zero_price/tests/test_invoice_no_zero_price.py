# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestInvoiceNoZeroPrice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.product = cls.env.ref("product.product_product_4")

    def _create_invoice(self, price_unit=100.0, allow_zero_price=False):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-01-01",
                "allow_zero_price": allow_zero_price,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "quantity": 1,
                            "price_unit": price_unit,
                        },
                    )
                ],
            }
        )

    def test_zero_price_blocks_posting(self):
        """Invoice with price_unit=0 should raise ValidationError on post."""
        invoice = self._create_invoice(price_unit=0.0)
        with self.assertRaises(ValidationError):
            invoice.action_post()

    def test_nonzero_price_posts_ok(self):
        """Invoice with price_unit > 0 should post without error."""
        invoice = self._create_invoice(price_unit=100.0)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_allow_zero_price_flag_bypasses_check(self):
        """Invoice with zero price should post if allow_zero_price is set."""
        invoice = self._create_invoice(price_unit=0.0, allow_zero_price=True)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
