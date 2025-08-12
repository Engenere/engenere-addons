from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    boleto_discount_perc = fields.Float(
        related="move_id.invoice_punctuality_discount",
    )
