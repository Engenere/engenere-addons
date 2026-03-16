from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestSaleFirstTimeState(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "list_price": 10.0}
        )
        cls.product_b = cls.env["product.product"].create(
            {"name": "Test Product B", "list_price": 20.0}
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
        order.write({"date_order": date_order})
        return order

    def _create_draft_order(self, product=None):
        product = product or self.product
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )

    # ------------------------------------------------------------------ #
    # Tests                                                               #
    # ------------------------------------------------------------------ #
    def test_first_sale_flag_first_time(self):
        """No previous sales: flag must be 'first_sale'."""
        order = self._create_draft_order()
        self.assertEqual(order.order_line.product_first_sale, "first_sale")

    def test_first_sale_flag_after_sale(self):
        """Previous confirmed sale exists: flag must be False."""
        self._create_confirmed_order()
        order = self._create_draft_order()
        self.assertFalse(order.order_line.product_first_sale)

    def test_first_sale_flag_days_limit(self):
        """Old sale outside days_limit: still marks 'first_sale'."""
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_first_sale.days_limit", 30
        )
        prod_old = self.env["product.product"].create(
            {"name": "Old Prod", "list_price": 8.0}
        )
        self._create_confirmed_order(days_ago=60, product=prod_old)
        order = self._create_draft_order(product=prod_old)
        self.assertEqual(order.order_line.product_first_sale, "first_sale")

    def test_flag_updates_on_product_change(self):
        """Flag must update when product is changed on existing line."""
        order = self._create_draft_order()
        line = order.order_line
        self.assertEqual(line.product_first_sale, "first_sale")

        # Confirm an order with product_b so it has previous sales
        self._create_confirmed_order(product=self.product_b)

        # Change product to product_b -> no longer first sale
        line.product_id = self.product_b
        self.assertFalse(line.product_first_sale)

    def test_flag_updates_to_first_sale_on_product_change(self):
        """Flag switches to first_sale when changing to a new product."""
        self._create_confirmed_order()
        order = self._create_draft_order()
        line = order.order_line
        self.assertFalse(line.product_first_sale)

        # Change to product_b which has no previous sale
        line.product_id = self.product_b
        self.assertEqual(line.product_first_sale, "first_sale")

    def test_show_first_sale_column_true(self):
        """Column is visible when at least one line has first_sale."""
        order = self._create_draft_order()
        self.assertTrue(order.show_first_sale_column)

    def test_show_first_sale_column_false(self):
        """Column is hidden when no line has first_sale."""
        self._create_confirmed_order()
        order = self._create_draft_order()
        self.assertFalse(order.show_first_sale_column)
