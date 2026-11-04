# Copyright 2026 Engenere - Felipe Motter Pereira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class L10nBrCNABReturnLog(models.Model):
    _inherit = "l10n_br_cnab.return.log"

    eng_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Journal",
        readonly=True,
    )
    eng_company_id = fields.Many2one(
        related="eng_journal_id.company_id",
        store=True,
        string="Company",
    )
    eng_file_hash = fields.Char(
        string="File Hash",
        readonly=True,
        copy=False,
        help="SHA-256 of the imported return file, unique per company and journal.",
    )

    _sql_constraints = [
        (
            "eng_file_hash_unique",
            "unique(eng_company_id, eng_journal_id, eng_file_hash)",
            "This CNAB return file was already imported in this journal.",
        ),
    ]
