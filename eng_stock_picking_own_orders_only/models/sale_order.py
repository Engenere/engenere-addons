from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_cancel(self):
        # Pre-cancel pickings as superuser so the upstream sale_stock call,
        # which does not sudo() the picking cancellation, does not raise
        # AccessError after we drop write rights on stock.picking from the
        # sale_salesman / sale_manager ACLs. The context flag short-circuits
        # the second action_cancel call inside the upstream method.
        self.picking_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
        ).sudo().action_cancel()
        return super(
            SaleOrder,
            self.with_context(eng_picking_lockdown_already_cancelled=True),
        )._action_cancel()
