from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_cancel(self):
        # Pre-cancel pickings as superuser so the upstream purchase_stock call,
        # which does not sudo() the picking cancellation, does not raise
        # AccessError after we drop write rights on stock.picking from the
        # purchase_user / purchase_manager ACLs. The upstream call still runs;
        # picking.action_cancel is a no-op when the moves are already in
        # cancel state.
        self.picking_ids.filtered(
            lambda r: r.state not in ("done", "cancel")
        ).sudo().action_cancel()
        return super(
            PurchaseOrder,
            self.with_context(eng_picking_lockdown_already_cancelled=True),
        ).button_cancel()
