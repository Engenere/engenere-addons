from datetime import timedelta

from odoo import fields
from odoo.tests.common import Form, TransactionCase


class TestSaleFirstTimeState(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "list_price": 10.0}
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _create_confirmed_order(self, days_ago=0, product=None):
        product = product or self.product
        date_order = fields.Datetime.now() - timedelta(days=days_ago)
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "date_order": date_order,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 10.0,
                            "name": "Test",
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        return order

    # ------------------------------------------------------------------ #
    # Tests                                                               #
    # ------------------------------------------------------------------ #
    def test_first_sale_flag_first_time(self):
        """Sem vendas anteriores ⇒ flag deve ser 'first_sale'."""
        form = Form(self.env["sale.order"])
        form.partner_id = self.partner
        with form.order_line.new() as line:
            line.product_id = self.product
            line.product_uom_qty = 1
        order = form.save()
        self.assertEqual(order.order_line.product_first_sale, "first_sale")

    def test_first_sale_flag_after_sale(self):
        """Venda já confirmada ⇒ flag não deve ser marcado."""
        self._create_confirmed_order()  # hoje
        form = Form(self.env["sale.order"])
        form.partner_id = self.partner
        with form.order_line.new() as line:
            line.product_id = self.product
            line.product_uom_qty = 1
        order = form.save()
        self.assertFalse(order.order_line.product_first_sale)

    def test_first_sale_flag_days_limit(self):
        """Venda antiga fora do limite ⇒ ainda marca 'first_sale'."""
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("sale_first_sale.days_limit", 30)

        # novo produto p/ isolar o teste
        prod_old = self.env["product.product"].create(
            {"name": "Old Prod", "list_price": 8.0}
        )

        # venda confirmada há 60 dias (fora do range de 30)
        self._create_confirmed_order(days_ago=60, product=prod_old)

        form = Form(self.env["sale.order"])
        form.partner_id = self.partner
        with form.order_line.new() as line:
            line.product_id = prod_old
            line.product_uom_qty = 1
        order = form.save()
        self.assertEqual(order.order_line.product_first_sale, "first_sale")
