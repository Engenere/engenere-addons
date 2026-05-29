from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user


class TestPickingReadonly(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Own Orders Partner"})
        cls.product = cls.env["product.product"].create(
            {"name": "Own Orders Product", "type": "product"}
        )

        cls.salesman = new_test_user(
            cls.env,
            login="readonly_salesman",
            groups="base.group_user,sales_team.group_sale_salesman",
        )
        cls.other_salesman = new_test_user(
            cls.env,
            login="readonly_other_salesman",
            groups="base.group_user,sales_team.group_sale_salesman",
        )
        cls.purchase_user = new_test_user(
            cls.env,
            login="readonly_purchase_user",
            groups="base.group_user,purchase.group_purchase_user",
        )
        cls.other_purchase_user = new_test_user(
            cls.env,
            login="readonly_other_purchase_user",
            groups="base.group_user,purchase.group_purchase_user",
        )
        cls.stock_user = new_test_user(
            cls.env,
            login="readonly_stock_user",
            groups="base.group_user,stock.group_stock_user",
        )
        cls.stock_manager = new_test_user(
            cls.env,
            login="readonly_stock_mgr",
            groups="base.group_user,stock.group_stock_manager",
        )
        cls.sale_manager = new_test_user(
            cls.env,
            login="readonly_sale_mgr",
            groups="base.group_user,sales_team.group_sale_manager",
        )
        cls.purchase_manager = new_test_user(
            cls.env,
            login="readonly_purchase_mgr",
            groups="base.group_user,purchase.group_purchase_manager",
        )
        cls.salesman_and_stock_user = new_test_user(
            cls.env,
            login="readonly_sales_and_stock",
            groups=(
                "base.group_user,"
                "sales_team.group_sale_salesman,"
                "stock.group_stock_user"
            ),
        )
        cls.faturista = new_test_user(
            cls.env,
            login="readonly_faturista",
            groups="base.group_user,account.group_account_invoice",
        )
        # Mirrors Bruna's real hat stack: salesman + buyer + invoicing, but no
        # stock role. The lockdown must hold against the union of those groups.
        cls.multi_hat = new_test_user(
            cls.env,
            login="readonly_multi_hat",
            groups=(
                "base.group_user,"
                "sales_team.group_sale_salesman,"
                "purchase.group_purchase_user,"
                "account.group_account_invoice"
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

    def test_salesman_sees_other_salesman_picking(self):
        # Sales role keeps broad picking visibility so they can inspect
        # transfers tied to any order (read-only, write is blocked by ACL).
        order = self._make_sale_order(self.other_salesman)
        order.with_user(self.other_salesman).action_confirm()
        other = order.picking_ids[:1]
        visible = self.env["stock.picking"].with_user(self.salesman).search([])
        self.assertIn(other, visible)

    def test_purchase_user_sees_own_purchase_picking(self):
        order = self._make_purchase_order(self.purchase_user)
        order.with_user(self.purchase_user).button_confirm()
        own = order.picking_ids[:1]
        visible = self.env["stock.picking"].with_user(self.purchase_user).search([])
        self.assertIn(own, visible)

    def test_purchase_user_sees_other_purchase_picking(self):
        # Purchase role keeps broad picking visibility for the same reason
        # as the sales role: read tied to any PO, write blocked by ACL.
        order = self._make_purchase_order(self.other_purchase_user)
        order.with_user(self.other_purchase_user).button_confirm()
        other = order.picking_ids[:1]
        visible = self.env["stock.picking"].with_user(self.purchase_user).search([])
        self.assertIn(other, visible)

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

    def test_salesman_sees_delivery_smart_button(self):
        # Upstream gates the Delivery smart button with stock.group_stock_user.
        # The module widens it to the salesman role, so a salesman who is NOT
        # a stock user still gets the button (group nodes are stripped per user
        # in get_view).
        arch = (
            self.env["sale.order"]
            .with_user(self.salesman)
            .get_view(view_type="form")["arch"]
        )
        tree = etree.fromstring(arch)
        self.assertTrue(
            tree.xpath("//button[@name='action_view_delivery']"),
            "salesman should see the delivery smart button",
        )

    def test_purchase_user_sees_receipt_button_but_not_receive_header(self):
        # The Receipt smart button is widened to purchase_user, but the
        # "Receive Products" header button (a write action, class oe_highlight)
        # is intentionally left gated to stock.group_stock_user. The buyer is
        # not a stock user, so the header button must be stripped while the
        # smart button (class oe_stat_button) survives.
        arch = (
            self.env["purchase.order"]
            .with_user(self.purchase_user)
            .get_view(view_type="form")["arch"]
        )
        tree = etree.fromstring(arch)
        self.assertTrue(
            tree.xpath(
                "//button[@name='action_view_picking']"
                "[contains(@class, 'oe_stat_button')]"
            ),
            "purchase_user should see the receipt smart button",
        )
        self.assertFalse(
            tree.xpath(
                "//button[@name='action_view_picking']"
                "[contains(@class, 'oe_highlight')]"
            ),
            "purchase_user must NOT see the Receive Products header button",
        )

    def _confirmed_sale_picking(self):
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        return order.picking_ids[:1]

    def _make_move_line(self, picking, move, user):
        return (
            self.env["stock.move.line"]
            .with_user(user)
            .create(
                {
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": self.product.id,
                    "product_uom_id": self.product.uom_id.id,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                    "qty_done": 1,
                }
            )
        )

    def _assert_cannot_touch_transfers(self, user):
        picking = self._confirmed_sale_picking()
        move = picking.move_ids[:1]
        with self.assertRaises(AccessError):
            picking.with_user(user).write({"scheduled_date": "2030-01-01 00:00:00"})
        with self.assertRaises(AccessError):
            move.with_user(user).write({"product_uom_qty": move.product_uom_qty + 1})
        with self.assertRaises(AccessError):
            self._make_move_line(picking, move, user)
        # An existing line (created by a stock user) is also not writable.
        move_line = self._make_move_line(picking, move, self.stock_user)
        with self.assertRaises(AccessError):
            move_line.with_user(user).write({"qty_done": 5})

    def test_faturista_cannot_edit_transfers(self):
        # The leak Felipe hit: Bruna is also a Faturista. That role must not
        # grant any edit on pickings, moves or move lines.
        self._assert_cannot_touch_transfers(self.faturista)

    def test_multi_hat_user_cannot_edit_transfers(self):
        # Full Bruna simulation: salesman + buyer + invoicing combined, no
        # stock role. The union of ACLs must still leave everything read-only.
        self._assert_cannot_touch_transfers(self.multi_hat)

    def test_stock_user_can_edit_move_line(self):
        # Dropping stock.move.line write from base.group_user must not affect
        # stock users, who keep it through their own ACL.
        picking = self._confirmed_sale_picking()
        move = picking.move_ids[:1]
        move_line = self._make_move_line(picking, move, self.stock_user)
        move_line.with_user(self.stock_user).write({"qty_done": 3})
        self.assertEqual(move_line.qty_done, 3)

    def test_salesman_confirm_with_stock_reserves_without_error(self):
        # Reservation creates stock.move.line during confirm. With move.line
        # write dropped from base.group_user, the assign step must still run
        # (procurement executes as superuser). A salesman confirming an order
        # for an in-stock product should reserve without AccessError.
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env["stock.quant"].sudo()._update_available_quantity(
            self.product, warehouse.lot_stock_id, 50
        )
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        picking = order.picking_ids[:1]
        self.assertTrue(
            picking.move_line_ids,
            "confirming with stock should reserve and create move lines",
        )

    def test_salesman_change_shipping_address_does_not_raise(self):
        # l10n_br_sale_stock propagates the shipping address to open pickings
        # with a picking write inside this onchange; the override elevates it so
        # a salesperson without picking write does not hit AccessError. In core
        # sale_stock (no l10n_br) the onchange only warns, so this asserts the
        # elevated wrapper runs cleanly for the office user.
        order = self._make_sale_order(self.salesman)
        order.with_user(self.salesman).action_confirm()
        order.with_user(self.salesman)._onchange_partner_shipping_id()
