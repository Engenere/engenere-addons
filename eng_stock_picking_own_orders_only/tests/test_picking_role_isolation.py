from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user


class TestPickingRoleIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Role Test Partner"})
        cls.product = cls.env["product.product"].create(
            {"name": "Role Test Product", "type": "product"}
        )

        cls.salesman = new_test_user(
            cls.env,
            login="picking_role_salesman",
            groups="base.group_user,sales_team.group_sale_salesman",
        )
        cls.other_salesman = new_test_user(
            cls.env,
            login="picking_role_other_salesman",
            groups="base.group_user,sales_team.group_sale_salesman",
        )
        cls.sale_manager = new_test_user(
            cls.env,
            login="picking_role_sale_mgr",
            groups="base.group_user,sales_team.group_sale_manager",
        )
        cls.purchase_user = new_test_user(
            cls.env,
            login="picking_role_purchase_user",
            groups="base.group_user,purchase.group_purchase_user",
        )
        cls.other_purchase_user = new_test_user(
            cls.env,
            login="picking_role_other_purchase_user",
            groups="base.group_user,purchase.group_purchase_user",
        )
        cls.stock_user = new_test_user(
            cls.env,
            login="picking_role_stock_user",
            groups="base.group_user,stock.group_stock_user",
        )
        cls.stock_manager = new_test_user(
            cls.env,
            login="picking_role_stock_mgr",
            groups="base.group_user,stock.group_stock_manager",
        )
        cls.salesman_and_stock_user = new_test_user(
            cls.env,
            login="picking_role_sales_and_stock",
            groups=(
                "base.group_user,"
                "sales_team.group_sale_salesman,"
                "stock.group_stock_user"
            ),
        )

    def _make_sale_picking(self, salesman_user):
        order = (
            self.env["sale.order"]
            .with_user(salesman_user)
            .create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 3,
                            },
                        )
                    ],
                }
            )
        )
        order.with_user(salesman_user).action_confirm()
        return order.picking_ids[:1]

    def _make_purchase_picking(self, purchase_user):
        order = (
            self.env["purchase.order"]
            .with_user(purchase_user)
            .create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "name": self.product.name,
                                "product_id": self.product.id,
                                "product_qty": 3,
                                "product_uom": self.product.uom_po_id.id,
                                "price_unit": 5.0,
                                "date_planned": "2026-06-01",
                            },
                        )
                    ],
                }
            )
        )
        order.with_user(purchase_user).button_confirm()
        return order.picking_ids[:1]

    def test_salesman_sees_own_sale_picking(self):
        own = self._make_sale_picking(self.salesman)
        visible = self.env["stock.picking"].with_user(self.salesman).search([])
        self.assertIn(own, visible)

    def test_salesman_does_not_see_other_salesman_picking(self):
        other = self._make_sale_picking(self.other_salesman)
        visible = self.env["stock.picking"].with_user(self.salesman).search([])
        self.assertNotIn(other, visible)

    def test_salesman_cannot_write_to_other_salesman_picking(self):
        other = self._make_sale_picking(self.other_salesman)
        with self.assertRaises(AccessError):
            other.with_user(self.salesman).write({"note": "leak"})

    def test_purchase_user_sees_own_purchase_picking(self):
        own = self._make_purchase_picking(self.purchase_user)
        visible = self.env["stock.picking"].with_user(self.purchase_user).search([])
        self.assertIn(own, visible)

    def test_purchase_user_does_not_see_other_purchase_picking(self):
        other = self._make_purchase_picking(self.other_purchase_user)
        visible = self.env["stock.picking"].with_user(self.purchase_user).search([])
        self.assertNotIn(other, visible)

    def test_stock_user_sees_everything(self):
        sale_picking = self._make_sale_picking(self.salesman)
        purchase_picking = self._make_purchase_picking(self.purchase_user)
        visible = self.env["stock.picking"].with_user(self.stock_user).search([])
        self.assertIn(sale_picking, visible)
        self.assertIn(purchase_picking, visible)

    def test_stock_manager_sees_everything(self):
        sale_picking = self._make_sale_picking(self.salesman)
        visible = self.env["stock.picking"].with_user(self.stock_manager).search([])
        self.assertIn(sale_picking, visible)

    def test_salesman_with_stock_user_sees_everything(self):
        other = self._make_sale_picking(self.other_salesman)
        visible = (
            self.env["stock.picking"].with_user(self.salesman_and_stock_user).search([])
        )
        self.assertIn(other, visible)

    def test_salesman_can_confirm_and_cancel_own_sale(self):
        order = (
            self.env["sale.order"]
            .with_user(self.salesman)
            .create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 2,
                            },
                        )
                    ],
                }
            )
        )
        order.with_user(self.salesman).action_confirm()
        pickings = order.picking_ids
        self.assertTrue(pickings)
        order.with_user(self.salesman)._action_cancel()
        for picking in pickings:
            self.assertEqual(picking.state, "cancel")

    def test_purchase_user_can_confirm_and_cancel_own_po(self):
        order = (
            self.env["purchase.order"]
            .with_user(self.purchase_user)
            .create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "name": self.product.name,
                                "product_id": self.product.id,
                                "product_qty": 2,
                                "product_uom": self.product.uom_po_id.id,
                                "price_unit": 5.0,
                                "date_planned": "2026-06-01",
                            },
                        )
                    ],
                }
            )
        )
        order.with_user(self.purchase_user).button_confirm()
        pickings = order.picking_ids
        self.assertTrue(pickings)
        order.with_user(self.purchase_user).button_cancel()
        for picking in pickings:
            self.assertEqual(picking.state, "cancel")
