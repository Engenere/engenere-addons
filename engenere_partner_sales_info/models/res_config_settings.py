from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    partner_sales_info_months = fields.Integer(
        string="Analysis Period (Months)",
        default=24,
        config_parameter="engenere_partner_sales_info.default_analysis_months",
    )
