# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Only select Partners approved for Sales
    partner_id = fields.Many2one(
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), ('stage_id.state', '=', 'confirmed')]",
    )
    partner_invoice_id = fields.Many2one(
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), ('stage_id.state', '=', 'confirmed')]",
    )

    @api.constrains("partner_id")
    def _check_partner_stage_confirmed(self):
        """Block order when partner stage is not confirmed."""
        for order in self:
            partner = order.partner_id
            if partner.stage_id and partner.stage_id.state != "confirmed":
                raise ValidationError(
                    _("Customer stage must be confirmed to create a sale order.")
                )
