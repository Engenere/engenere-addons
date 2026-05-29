from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _create_stock_moves(self, picking):
        # Leaf shared by both PO move-creation paths: button_approve ->
        # purchase.order._create_picking() (confirm) and the confirmed-PO
        # quantity bump. After we drop create on stock.move from the purchase
        # roles, this server-driven procurement step would raise for a buyer.
        # The picking itself is already created by core with SUPERUSER_ID, so
        # only the move creation (and the reservation/assign that runs on the
        # returned recordset) needs elevation.
        return super(PurchaseOrderLine, self.sudo())._create_stock_moves(picking.sudo())

    def _create_or_update_picking(self):
        # Intentional whole-method privilege elevation. The upstream method
        # creates a stock.picking, then calls _create_stock_moves(),
        # _action_confirm() and _action_assign() on the spawned moves, plus
        # an activity write on the related vendor bill. All of these can
        # fail for a purchase user after we drop write/create/unlink on
        # stock.picking. Kept in addition to the _create_stock_moves hook
        # because the qty-bump path creates the picking itself without sudo
        # when no open picking exists. The method is internal to
        # purchase_stock and only fires from PO line write flows (qty bump on
        # a confirmed PO), so the elevated execution is bounded to a
        # legitimate, server-driven path and not exposed to user-supplied RPC
        # arguments.
        return super(PurchaseOrderLine, self.sudo())._create_or_update_picking()
