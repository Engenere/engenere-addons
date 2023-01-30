# Copyright (C) 2023-Today - Engenere (<https://engenere.one>).
# @author Felipe Motter Pereira <felipe@engenere.one>

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    partner_order = fields.Text(
        compute="_compute_partner_order",
        store=True,
        readonly=False,
    )

    @api.model
    def create(self, vals):
        if "partner_order" not in vals and "order_id" in vals:
            sale_order = self.env["sale.order"].browse(vals["order_id"])
            if sale_order.client_order_ref:
                vals["partner_order"] = sale_order.client_order_ref
        return super().create(vals)

    @api.depends("order_id", "order_id.client_order_ref")
    def _compute_partner_order(self):
        # if hasattr(super(), "_compute_partner_order"):
        #     super()._compute_partner_order()
        for line in self:
            line.partner_order = line.order_id.client_order_ref
