# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountMove(models.Model):

    _inherit = "account.move"

    def generate_combined_pdf(self):
        self.ensure_one()
        return self.fiscal_document_id.generate_combined_pdf()
