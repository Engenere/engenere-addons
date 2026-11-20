# Copyright 2026 Engenere.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _check_commitment_date_required(self):
        """Refuse to confirm an order without a delivery date, in the companies
        that ask for it."""
        orders = self.filtered(
            lambda order: order.company_id.sale_commitment_date_required
            and not order.commitment_date
        )
        if orders:
            raise UserError(
                _(
                    "Set the delivery date before confirming: %(orders)s.",
                    orders=", ".join(orders.mapped("name")),
                )
            )

    def action_confirm(self):
        self._check_commitment_date_required()
        return super().action_confirm()
