# Copyright 2026 Engenere.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sale_commitment_date_required = fields.Boolean(
        string="Require Delivery Date to Confirm Sales Orders",
        help="A sales order of this company cannot be confirmed without a"
        " delivery date.",
    )
