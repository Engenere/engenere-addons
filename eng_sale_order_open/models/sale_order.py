# Copyright 2026 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_open = fields.Boolean(
        string="Open",
        compute="_compute_is_open",
        store=True,
        help="Confirmed order with pending delivery or pending invoice.",
    )

    @api.depends(
        "state",
        "invoice_status",
        "picking_ids.state",
        "order_line.qty_to_invoice",
        "order_line.qty_invoiced",
        "order_line.qty_delivered",
    )
    def _compute_is_open(self):
        for order in self:
            if order.state not in ("sale", "done"):
                order.is_open = False
                continue
            pending_delivery = any(
                p.state not in ("done", "cancel") for p in order.picking_ids
            )
            # Pending invoice only when Odoo does not consider the order fully
            # invoiced AND there is still quantity to invoice. The first check
            # honors manual overrides like ``force_invoiced`` (which forces
            # ``invoice_status='invoiced'``); the second handles short-shipment
            # tolerances where ``invoice_status`` stays ``'no'`` even with
            # nothing left to invoice.
            pending_invoice = order.invoice_status != "invoiced" and any(
                line.qty_to_invoice for line in order.order_line
            )
            # An order with no net activity (nothing delivered and nothing
            # invoiced) is treated as still open even with no pending action:
            # covers freshly-confirmed orders and full-reversal scenarios
            # (delivered + returned and invoiced + refunded back to zero)
            # where the user is expected to explicitly cancel the order.
            # Skip this rule when ``invoice_status='invoiced'`` — that signals
            # the user has explicitly closed the invoice side (typically via
            # ``force_invoiced`` from ``sale_force_invoiced``), so the order
            # should close even with zero delivered/invoiced quantities.
            has_net_activity = any(
                line.qty_delivered or line.qty_invoiced for line in order.order_line
            )
            no_activity_open = (
                not has_net_activity and order.invoice_status != "invoiced"
            )
            order.is_open = pending_delivery or pending_invoice or no_activity_open
