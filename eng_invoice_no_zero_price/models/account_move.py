# Copyright 2026 Engenere
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    allow_zero_price = fields.Boolean(
        default=False,
    )

    @api.constrains("state", "invoice_line_ids")
    def _check_invoice_line_zero_price(self):
        for move in self:
            if move.move_type != "out_invoice" or move.state != "posted":
                continue
            if move.allow_zero_price:
                continue
            zero_lines = move.invoice_line_ids.filtered(
                lambda line: line.display_type == "product" and line.price_unit == 0.0
            )
            if zero_lines:
                product_names = ", ".join(
                    line.product_id.display_name or line.name for line in zero_lines
                )
                raise ValidationError(
                    _(
                        "The following products have zero price: %s",
                        product_names,
                    )
                )
