from odoo import fields, models


class AccountPaymentMode(models.Model):
    _inherit = "l10n_br_cnab.config"

    filename_sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Sequência do nome do arquivo",
        tracking=True,
    )
