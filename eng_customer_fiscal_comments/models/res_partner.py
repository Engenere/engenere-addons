from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    fiscal_comments = fields.Text()
