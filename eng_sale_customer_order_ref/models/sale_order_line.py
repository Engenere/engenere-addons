# Copyright (C) 2023-Today - Engenere (<https://engenere.one>).
# @author Felipe Motter Pereira <felipe@engenere.one>

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Not copied, like the customer reference of the order it comes from
    partner_order = fields.Char(
        compute="_compute_partner_order", store=True, readonly=False, copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        # An empty partner order is not a choice of the user: the line form
        # opened on a new line sends it empty, which would skip the compute
        for vals in vals_list:
            if not vals.get("partner_order"):
                vals.pop("partner_order", None)
        return super().create(vals_list)

    @api.depends("order_id", "order_id.client_order_ref")
    def _compute_partner_order(self):
        for record in self:
            record.partner_order = (
                record.order_id.client_order_ref if record.order_id else False
            )
