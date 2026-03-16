# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    product_first_sale = fields.Selection(
        selection=[("first_sale", _("First Sale"))],
        string="First Sale?",
        compute="_compute_product_first_sale",
        store=True,
    )

    @api.depends("product_id", "order_id.partner_id")
    def _compute_product_first_sale(self):
        """Flag if it's the first time the partner buys this product."""
        Param = self.env["ir.config_parameter"].sudo()
        days_limit = int(Param.get_param("sale_first_sale.days_limit", default=0))

        for line in self:
            partner = line.order_id.partner_id
            if (
                line.order_id.state in ("sale", "done")
                or not line.product_id
                or not partner
            ):
                line.product_first_sale = False
                continue

            domain = [
                ("product_id", "=", line.product_id.id),
                ("order_partner_id", "=", partner.id),
                ("order_id.state", "in", ["sale", "done"]),
                ("product_uom_qty", ">", 0),
            ]
            if days_limit:
                date_limit = fields.Datetime.now() - timedelta(days=days_limit)
                domain.append(("order_id.date_order", ">=", date_limit))

            has_prev = bool(self.env["sale.order.line"].search_count(domain))
            line.product_first_sale = False if has_prev else "first_sale"
