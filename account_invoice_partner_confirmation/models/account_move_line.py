# Copyright 2023 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class AccountMoveLine(models.Model):

    _inherit = "account.move.line"

    part_confirm_date = fields.Date(
        "Confirmation Date",
        related="move_id.part_confirm_date",
        store=True
    )


