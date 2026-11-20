# Copyright (C) 2023-Today - Engenere (<https://engenere.one>).
# @author Felipe Motter Pereira <felipe@engenere.one>

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Not copied, like the customer reference of the order it comes from
    partner_order = fields.Char(
        compute="_compute_partner_order", store=True, readonly=False, copy=False
    )

    @api.depends("order_id", "order_id.client_order_ref")
    def _compute_partner_order(self):
        for record in self:
            record.partner_order = (
                record.order_id.client_order_ref if record.order_id else False
            )
