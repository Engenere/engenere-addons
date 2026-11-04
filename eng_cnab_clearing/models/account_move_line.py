# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Set only on the clearing line of a clearing entry, whose due date
    # (date_maturity) is the credit date of the liquidation
    eng_cnab_clearing = fields.Boolean(
        string="CNAB Clearing Line",
        copy=False,
        readonly=True,
        help="Clearing account line of a CNAB return liquidation, due on its "
        "credit date, waiting for the bank statement.",
    )
    eng_cnab_receiving_bank_class = fields.Selection(
        selection=[("own", "Own Bank"), ("other", "Other Banks")],
        string="Receiving Bank Class",
        copy=False,
        readonly=True,
        help="Whether the title was paid at the bank of the journal or at "
        "another bank, from the receiving bank of the CNAB return. Empty when "
        "the return does not state it.",
    )
    eng_cnab_return_event_id = fields.Many2one(
        comodel_name="l10n_br_cnab.return.event",
        string="CNAB Return Event",
        copy=False,
        readonly=True,
    )
