# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    show_first_sale_column = fields.Boolean(compute="_compute_show_first_sale_column")

    @api.depends("order_line.product_first_sale")
    def _compute_show_first_sale_column(self):
        for order in self:
            order.show_first_sale_column = bool(
                order.order_line.filtered("product_first_sale")
            )
