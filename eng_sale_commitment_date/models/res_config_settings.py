# Copyright 2026 Engenere.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sale_commitment_date_required = fields.Boolean(
        related="company_id.sale_commitment_date_required",
        readonly=False,
    )
