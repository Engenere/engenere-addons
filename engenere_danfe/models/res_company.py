# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    danfe_library = fields.Selection(
        selection_add=[("engenere_danfe", "Danfe Engenere")]
    )
