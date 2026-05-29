from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_cancel(self):
        # When sale.order._action_cancel / purchase.order.button_cancel
        # pre-cancel the pickings as superuser, the upstream sale_stock /
        # purchase_stock methods still call action_cancel on the same
        # recordset without sudo. Honour the flag set by those overrides
        # and short-circuit only when the pickings are actually cancelled,
        # so the flag cannot be forged via RPC to skip a real cancellation.
        if self.env.context.get("eng_picking_lockdown_already_cancelled") and all(
            picking.state == "cancel" for picking in self
        ):
            return True
        return super().action_cancel()
