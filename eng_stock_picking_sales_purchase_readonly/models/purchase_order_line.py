from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _create_or_update_picking(self):
        # Intentional whole-method privilege elevation. The upstream method
        # creates a stock.picking, then calls _create_stock_moves(),
        # _action_confirm() and _action_assign() on the spawned moves, plus
        # an activity write on the related vendor bill. All of these can
        # fail for a purchase user after we drop write/create/unlink on
        # stock.picking. The method is internal to purchase_stock and only
        # fires from PO line write flows (qty bump on a confirmed PO), so
        # the elevated execution is bounded to a legitimate, server-driven
        # path and not exposed to user-supplied RPC arguments.
        return super(PurchaseOrderLine, self.sudo())._create_or_update_picking()
