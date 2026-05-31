# Copyright 2026 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestSaleOrderOpen(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(
        cls, chart_template_ref="l10n_br_coa_generic.l10n_br_coa_generic_template"
    ):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.product_storable = cls.env["product.product"].create(
            {
                "name": "Storable Test Product",
                "type": "product",
                "list_price": 10.0,
                "invoice_policy": "delivery",
            }
        )
        cls.product_service = cls.env["product.product"].create(
            {
                "name": "Service Test Product",
                "type": "service",
                "list_price": 10.0,
                "invoice_policy": "order",
            }
        )

    def _create_order(self, product=None, qty=1.0):
        product = product or self.product_storable
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": 10.0,
                            "name": "Test",
                        },
                    )
                ],
            }
        )

    def _close_pickings(self, order, qty_done):
        """Validate every picking with `qty_done`, never creating a backorder.

        ``cancel_backorder`` makes ``_action_done`` deliver only ``qty_done``
        and cancel the remaining balance instead of spawning a backorder, so
        a short shipment leaves a single ``done`` picking.
        """
        for picking in order.picking_ids:
            for move in picking.move_ids:
                move.quantity_done = qty_done
            picking.with_context(cancel_backorder=True)._action_done()

    def test_quotation_is_not_open(self):
        order = self._create_order()
        self.assertFalse(order.is_open)

    def test_cancelled_is_not_open(self):
        order = self._create_order()
        order.action_confirm()
        order._action_cancel()
        self.assertFalse(order.is_open)

    def test_confirmed_with_open_picking_is_open(self):
        order = self._create_order()
        order.action_confirm()
        self.assertTrue(order.picking_ids)
        self.assertTrue(
            any(p.state not in ("done", "cancel") for p in order.picking_ids)
        )
        self.assertTrue(order.is_open)

    def test_pickings_done_but_not_invoiced_is_open(self):
        """All pickings closed but invoice still pending → open (driven by invoice)."""
        order = self._create_order(qty=10)
        order.action_confirm()
        self._close_pickings(order, qty_done=10)
        self.assertTrue(all(p.state == "done" for p in order.picking_ids))
        self.assertNotEqual(order.invoice_status, "invoiced")
        self.assertTrue(order.is_open)

    def test_short_shipment_with_invoice_is_not_open(self):
        """Short shipment closed without backorder and invoiced for the
        delivered qty: qty_to_invoice drops to 0 and the order is considered
        closed even though qty_delivered < product_uom_qty (invoice_status
        stays 'no').
        """
        order = self._create_order(qty=10)
        order.action_confirm()
        self._close_pickings(order, qty_done=7)
        self.assertTrue(all(p.state == "done" for p in order.picking_ids))
        self.assertEqual(sum(order.order_line.mapped("qty_delivered")), 7)
        invoice = order._create_invoices()
        invoice.action_post()
        order.invalidate_recordset(["invoice_status", "is_open"])
        self.assertEqual(sum(order.order_line.mapped("qty_to_invoice")), 0)
        self.assertFalse(order.is_open)

    def test_service_policy_order_open_until_invoiced(self):
        """Service with policy='order' has qty_to_invoice > 0 right after
        confirm and closes once fully invoiced."""
        order = self._create_order(product=self.product_service)
        order.action_confirm()
        self.assertFalse(order.picking_ids)
        self.assertGreater(sum(order.order_line.mapped("qty_to_invoice")), 0)
        self.assertTrue(order.is_open)
        invoice = order._create_invoices()
        invoice.action_post()
        order.invalidate_recordset(["invoice_status", "is_open"])
        self.assertEqual(order.invoice_status, "invoiced")
        self.assertFalse(order.is_open)

    def test_force_invoiced_with_no_activity_is_not_open(self):
        """``force_invoiced`` (from ``sale_force_invoiced``) sets
        ``invoice_status='invoiced'`` even with zero delivered/invoiced
        quantities. That signals the user has explicitly closed the invoice
        side, so the no-net-activity heuristic must yield and the order
        closes."""
        if "force_invoiced" not in self.env["sale.order"]._fields:
            self.skipTest("sale_force_invoiced not installed")
        order = self._create_order(product=self.product_service)
        order.action_confirm()
        self.assertTrue(order.is_open)
        order.force_invoiced = True
        order.invalidate_recordset(["invoice_status", "is_open"])
        self.assertEqual(order.invoice_status, "invoiced")
        self.assertEqual(sum(order.order_line.mapped("qty_invoiced")), 0)
        self.assertEqual(sum(order.order_line.mapped("qty_delivered")), 0)
        self.assertFalse(order.is_open)

    def test_service_policy_delivery_no_activity_is_open(self):
        """Service with policy='delivery' freshly confirmed has no pickings,
        no invoices, qty_delivered=0 and qty_to_invoice=0. The order has no
        net activity and must stay open until something happens."""
        service_delivery = self.env["product.product"].create(
            {
                "name": "Service Delivery",
                "type": "service",
                "list_price": 10.0,
                "invoice_policy": "delivery",
            }
        )
        order = self._create_order(product=service_delivery)
        order.action_confirm()
        self.assertFalse(order.picking_ids)
        self.assertFalse(order.invoice_ids)
        self.assertEqual(sum(order.order_line.mapped("qty_to_invoice")), 0)
        self.assertEqual(sum(order.order_line.mapped("qty_delivered")), 0)
        self.assertTrue(order.is_open)
