# Copyright (C) 2023-Today - Engenere (<https://engenere.one>).
# @author Felipe Motter Pereira <felipe@engenere.one>

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    partner_order = fields.Char(
        compute="_compute_partner_order", store=True, readonly=False
    )

    @api.depends("order_id", "order_id.client_order_ref")
    def _compute_partner_order(self):
        for record in self:
            record.partner_order = (
                record.order_id.client_order_ref if record.order_id else False
            )
