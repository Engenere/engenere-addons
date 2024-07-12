# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class L10nBrFiscalDocument(models.Model):

    _inherit = "l10n_br_fiscal.document"

    fiscal_tax_engine_disabled = fields.Boolean(
        string="Fiscal Tax Engine Disabled", default=False
    )
