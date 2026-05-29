from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user


class TestPickingOwnOrdersOnly(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Own Orders Partner"})
        cls.product = cls.env["product.product"].create(
            {"name": "Own Orders Product", "type": "product"}
        )

        cls.salesman = new_test_user(
            cls.env,
            login="own_orders_salesman",
            groups="base.group_user,sales_team.group_sale_salesman",
        )
        cls.other_salesman = new_test_user(
            cls.env,
            login="own_orders_other_salesman",
            groups="base.group_user,sales_team.group_sale_salesman",
        )
        cls.purchase_user = new_test_user(
            cls.env,
            login="own_orders_purchase_user",
            groups="base.group_user,purchase.group_purchase_user",
        )
        cls.other_purchase_user = new_test_user(
            cls.env,
            login="own_orders_other_purchase_user",
            groups="base.group_user,purchase.group_purchase_user",
        )
        cls.stock_user = new_test_user(
            cls.env,
            login="own_orders_stock_user",
            groups="base.group_user,stock.group_stock_user",
        )
        cls.stock_manager = new_test_user(
            cls.env,
            login="own_orders_stock_mgr",
            groups="base.group_user,stock.group_stock_manager",
        )
        cls.sale_manager = new_test_user(
            cls.env,
            login="own_orders_sale_mgr",
            groups="base.group_user,sales_team.group_sale_manager",
        )
        cls.purchase_manager = new_test_user(
            cls.env,
            login="own_orders_purchase_mgr",
            groups="base.group_user,purchase.group_purchase_manager",
        )
        cls.salesman_and_stock_user = new_test_user(
            cls.env,
            login="own_orders_sales_and_stock",
            groups=(
                "base.group_user,"
                "sales_team.group_sale_salesman,"
                "stock.group_stock_user"
            ),
        )

    def _make_sale_order(self, user):
        return (
            self.env["sale.order"]
            .with_user(user)
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

    def _make_purchase_order(self, user):
        return (
            self.env["purchase.order"]
            .with_user(user)
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

    def test_salesman_cannot_write_picking_directly(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        picking = order.picking_ids[:1]
        with self.assertRaises(AccessError):
            picking.with_user(self.salesman).write({"note": "leak"})

    def test_salesman_cannot_unlink_picking(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        picking = order.picking_ids[:1]
        with self.assertRaises(AccessError):
            picking.with_user(self.salesman).unlink()

    def test_salesman_cannot_create_picking(self):
        picking_type = self.env.ref("stock.picking_type_out")
        with self.assertRaises(AccessError):
            self.env["stock.picking"].with_user(self.salesman).create(
                {
                    "partner_id": self.partner.id,
                    "picking_type_id": picking_type.id,
                    "location_id": picking_type.default_location_src_id.id,
                    "location_dest_id": picking_type.default_location_dest_id.id,
                }
            )

    def test_salesman_can_confirm_sale_creating_picking(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        self.assertTrue(order.picking_ids)
        self.assertEqual(order.state, "sale")

    def test_salesman_can_cancel_sale_cancelling_picking(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        pickings = order.picking_ids
        order.with_user(self.salesman)._action_cancel()
        for picking in pickings:
            self.assertEqual(picking.state, "cancel")

    def test_purchase_user_cannot_write_picking_directly(self):
        order = self._make_purchase_order(self.purchase_user)
        order.with_user(self.purchase_user).button_confirm()
        picking = order.picking_ids[:1]
        with self.assertRaises(AccessError):
            picking.with_user(self.purchase_user).write({"note": "leak"})

    def test_purchase_user_can_confirm_po_creating_picking(self):
        order = self._make_purchase_order(self.purchase_user)
        order.with_user(self.purchase_user).button_confirm()
        self.assertTrue(order.picking_ids)

    def test_purchase_user_can_cancel_po_cancelling_picking(self):
        order = self._make_purchase_order(self.purchase_user)
        order.with_user(self.purchase_user).button_confirm()
        pickings = order.picking_ids
        order.with_user(self.purchase_user).button_cancel()
        for picking in pickings:
            self.assertEqual(picking.state, "cancel")

    def test_purchase_user_can_increase_qty_on_confirmed_po(self):
        order = self._make_purchase_order(self.purchase_user)
        order.with_user(self.purchase_user).button_confirm()
        line = order.order_line[0]
        line.with_user(self.purchase_user).write({"product_qty": 10})
        total_qty = sum(order.picking_ids.move_ids.mapped("product_uom_qty"))
        self.assertEqual(total_qty, 10)

    def test_salesman_sees_own_sale_picking(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        own = order.picking_ids[:1]
        visible = self.env["stock.picking"].with_user(self.salesman).search([])
        self.assertIn(own, visible)

    def test_salesman_does_not_see_other_salesman_picking(self):
        order = self._make_sale_order(self.other_salesman)
        order.with_user(self.other_salesman).action_confirm()
        other = order.picking_ids[:1]
        visible = self.env["stock.picking"].with_user(self.salesman).search([])
        self.assertNotIn(other, visible)

    def test_purchase_user_sees_own_purchase_picking(self):
        order = self._make_purchase_order(self.purchase_user)
        order.with_user(self.purchase_user).button_confirm()
        own = order.picking_ids[:1]
        visible = self.env["stock.picking"].with_user(self.purchase_user).search([])
        self.assertIn(own, visible)

    def test_purchase_user_does_not_see_other_purchase_picking(self):
        order = self._make_purchase_order(self.other_purchase_user)
        order.with_user(self.other_purchase_user).button_confirm()
        other = order.picking_ids[:1]
        visible = self.env["stock.picking"].with_user(self.purchase_user).search([])
        self.assertNotIn(other, visible)

    def test_stock_user_can_write_picking(self):
        sale = self._make_sale_order(self.salesman)
        sale.with_user(self.salesman).action_confirm()
        picking = sale.picking_ids[:1]
        picking.with_user(self.stock_user).write({"note": "stock note"})

    def test_sale_manager_cannot_write_picking_directly(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        picking = order.picking_ids[:1]
        with self.assertRaises(AccessError):
            picking.with_user(self.sale_manager).write({"note": "mgr leak"})

    def test_sale_manager_can_cancel_own_sale(self):
        order = self._make_sale_order(self.sale_manager)
        order.with_user(self.sale_manager).action_confirm()
        pickings = order.picking_ids
        order.with_user(self.sale_manager)._action_cancel()
        for picking in pickings:
            self.assertEqual(picking.state, "cancel")

    def test_purchase_manager_cannot_write_picking_directly(self):
        order = self._make_purchase_order(self.purchase_user)
        order.with_user(self.purchase_user).button_confirm()
        picking = order.picking_ids[:1]
        with self.assertRaises(AccessError):
            picking.with_user(self.purchase_manager).write({"note": "mgr leak"})

    def test_purchase_manager_can_cancel_own_po(self):
        order = self._make_purchase_order(self.purchase_manager)
        order.with_user(self.purchase_manager).button_confirm()
        pickings = order.picking_ids
        order.with_user(self.purchase_manager).button_cancel()
        for picking in pickings:
            self.assertEqual(picking.state, "cancel")

    def test_salesman_with_stock_user_can_edit_any_picking(self):
        # An internal user who is both salesman AND stock operator should
        # keep full picking write rights via the stock.group_stock_user ACL,
        # even when the salesman ACL is locked down.
        order = self._make_sale_order(self.other_salesman)
        order.with_user(self.other_salesman).action_confirm()
        other_picking = order.picking_ids[:1]
        other_picking.with_user(self.salesman_and_stock_user).write(
            {"note": "stock-user edit"}
        )

    def test_action_cancel_skip_flag_cannot_be_forged(self):
        # The eng_picking_lockdown_already_cancelled context flag must only
        # short-circuit action_cancel when the pickings are actually in
        # cancel state. A salesman trying to fake-cancel a picking via RPC
        # must still hit the upstream cancellation (and fail on ACL).
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        picking = order.picking_ids[:1]
        with self.assertRaises(AccessError):
            picking.with_user(self.salesman).with_context(
                eng_picking_lockdown_already_cancelled=True
            ).action_cancel()
        self.assertNotEqual(picking.state, "cancel")

    def test_stock_manager_can_unlink_cancelled_picking(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        picking = order.picking_ids[:1]
        order.with_user(self.salesman)._action_cancel()
        picking.with_user(self.stock_manager).unlink()
