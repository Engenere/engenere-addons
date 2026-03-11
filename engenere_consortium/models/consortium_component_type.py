# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ConsortiumComponentType(models.Model):
    _name = "consortium.component.type"
    _description = "Consortium Component Type"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    account_type = fields.Selection(
        selection=[
            ("liability", "Liability"),
            ("expense", "Expense"),
            ("asset", "Asset"),
        ],
    )
    default_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Default Account",
    )

    _sql_constraints = [
        (
            "code_uniq",
            "UNIQUE(code)",
            "The code must be unique.",
        ),
    ]
