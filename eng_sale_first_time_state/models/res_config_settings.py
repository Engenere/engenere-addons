# Copyright 2025 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sale_first_sale_days_limit = fields.Integer(
        string="Limit Days for First Sale",
        config_parameter="sale_first_sale.days_limit",
    )
