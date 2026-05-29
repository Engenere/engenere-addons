from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.onchange("partner_shipping_id")
    def _onchange_partner_shipping_id(self):
        # Core sale_stock only warns here, but l10n_br_sale_stock overrides
        # this onchange to propagate the shipping address to the open pickings
        # with a direct picking write. Elevate the whole (small, read-only in
        # core) onchange so a salesperson, who no longer has stock.picking
        # write, can still correct the delivery address on a confirmed order:
        # the address is order data, not a stock decision. The @api.onchange
        # decorator is re-applied because overriding the method without it
        # would unregister the trigger.
        return super(SaleOrder, self.sudo())._onchange_partner_shipping_id()

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
