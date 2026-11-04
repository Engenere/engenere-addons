# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class L10nBrCNABReturnEvent(models.Model):
    _inherit = "l10n_br_cnab.return.event"

    eng_record_position = fields.Integer(
        string="Position in File",
        readonly=True,
        help="Position of the record in the return file, as listed by the "
        "BRCobranca API (1 is the first record after the file header).",
    )
    eng_receiving_bank_code = fields.Char(
        string="Receiving Bank Code",
        readonly=True,
        help="Receiving bank exactly as returned by the BRCobranca API.",
    )
    eng_receiving_branch_code = fields.Char(
        string="Receiving Branch Code",
        readonly=True,
        help="Receiving branch exactly as returned by the BRCobranca API.",
    )
    eng_move_id = fields.Many2one(
        comodel_name="account.move",
        string="CNAB Clearing Entry",
        readonly=True,
    )
